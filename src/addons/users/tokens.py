"""
tokens.py — addons.users

PYTokenObtainPairView: login personalizado con:
  FR-AUTH-02.01: rate limiting por IP (max 5 intentos fallidos / 15 min)
  FR-AUTH-02.07: normalización del identificador a minúsculas
  FR-AUTH-02.09: mensaje diferenciado para email no verificado
  FR-AUTH-02.14: restablecimiento del contador tras login exitoso
  FR-AUTH-02.15: objeto 'user' en la respuesta

PYTokenRefreshView: refresh con validacion is_active.
  Cierra D-26 del audit T-102 (refresh-validar-user-activo).
  Sin esta validacion, simplejwt emite nuevo access aunque
  el usuario haya sido suspendido (privilege-after-suspend
  window hasta 7 dias). Ver DEC-REF-1..4.
"""
import hashlib
from django.contrib.auth import get_user_model, login as django_login

from addons.authz.services import is_superadmin
from addons.authz_totp.services import consume_recovery_code, totp_enabled, verify_code
from django.contrib.auth.models import update_last_login
from django.core.cache import cache
from .session_tracking import record_user_session
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenBlacklistView, TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from .audit import audit_log_auth
from .models import AuthEvent

User = get_user_model()

# ─── Constantes de rate limiting ──────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW      = 15 * 60   # 15 minutos en segundos
LOCKOUT_DURATION    = 15 * 60   # 15 minutos de bloqueo


def _ip_cache_key(ip: str) -> str:
    """Clave de cache: hash de la IP para no almacenar IPs en claro."""
    return f'login_fails:{hashlib.sha256(ip.encode()).hexdigest()}'


def get_client_ip(request) -> str:
    """Extrae la IP real del cliente considerando proxies."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def check_login_rate_limit(ip: str):
    """
    FR-AUTH-02.01: verifica si la IP está bloqueada.
    Retorna los segundos restantes de bloqueo (0 si no está bloqueada).
    """
    key = _ip_cache_key(ip)
    count = cache.get(key, 0)
    if count >= MAX_FAILED_ATTEMPTS:
        return LOCKOUT_DURATION
    return 0


def record_failed_attempt(ip: str):
    """Incrementa el contador de intentos fallidos para la IP."""
    key = _ip_cache_key(ip)
    count = cache.get(key, 0)
    cache.set(key, count + 1, timeout=LOCKOUT_WINDOW)


def reset_failed_attempts(ip: str):
    """FR-AUTH-02.14: limpia el contador tras login exitoso."""
    cache.delete(_ip_cache_key(ip))


class PYTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer de login con rate limiting, normalización y datos de usuario.
    La IP se pasa via context['request'] desde la view.
    """

    def validate(self, attrs):
        # FR-AUTH-02.07 — normalizar a minúsculas
        username = attrs.get(self.username_field, '').strip().lower()
        attrs[self.username_field] = username

        # FR-AUTH-02.09 — detectar email no verificado
        try:
            # Party (T-201): el identificador es email (USERNAME_FIELD); ``username``
            # aquí es el valor del credential (el email normalizado).
            user = User.objects.get(email__iexact=username)
            if not user.is_active and user.has_usable_password():
                raise AuthenticationFailed(
                    detail={
                        # T-103 iter 16 (canon EN per UC-AUTH-02:601):
                        # key 'codigo' -> 'codigo_error', valor
                        # 'EMAIL_NO_VERIFICADO' -> 'EMAIL_NOT_VERIFIED'.
                        'codigo_error': 'EMAIL_NOT_VERIFIED',
                        'mensaje': (
                            'Tu cuenta aún no está activada. '
                            'Revisa tu email y haz clic en el enlace de verificación.'
                        ),
                    },
                    code='email_no_verificado',
                )
        except User.DoesNotExist:
            # silent OK because anti-user-enumeration: super().validate()
            # devolvera AuthenticationFailed con mensaje generico, sin
            # revelar si el username existe. DEC-DOC-008.
            pass

        data = super().validate(attrs)

        # authz_totp (DEC-01, ~auth_totp de Odoo): segundo factor DESPUÉS de
        # verificar la contraseña. Si el usuario tiene 2FA activo, exige un
        # código TOTP válido; sin él, el login NO se completa (no se emiten
        # tokens). Data-driven: sólo aplica a usuarios con 2FA (sin regresión).
        if totp_enabled(self.user):
            otp = str(self.initial_data.get('otp', '') or '').strip()
            if not otp:
                raise AuthenticationFailed(
                    detail={'codigo_error': 'TOTP_REQUIRED',
                            'mensaje': 'Ingresa el código de verificación de dos pasos.'},
                    code='totp_required',
                )
            # Acepta un código TOTP actual O un código de recuperación de un
            # solo uso (~auth_totp de Odoo): si el usuario perdió el
            # authenticator, uno de sus backup codes lo deja entrar.
            if not verify_code(self.user, otp) and not consume_recovery_code(self.user, otp):
                raise AuthenticationFailed(
                    detail={'codigo_error': 'TOTP_INVALID',
                            'mensaje': 'Código de verificación inválido.'},
                    code='totp_invalid',
                )

        # D-09 fix (audit-log-eventos-auth, DEC-AL-6):
        # simplejwt no actualiza last_login por default.
        # POST-05 UC-AUTH-02 lo requiere.
        update_last_login(None, self.user)

        # FR-AUTH-02.15 — añadir objeto user a la respuesta
        user = self.user
        data['user'] = {
            'id':         user.pk,
            'username':   user.email,
            'email':      user.email,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'is_staff':   is_superadmin(user),
            'avatar_url': user.get_avatar_url(),
        }
        return data


class PYTokenObtainPairView(TokenObtainPairView):
    """
    View de login con rate limiting por IP (FR-AUTH-02.01 / FR-AUTH-02.14).
    Emite AuthEvent LOGIN_SUCCESS / LOGIN_FAIL (D-10).
    """
    serializer_class = PYTokenObtainPairSerializer

    def _audit_login(self, request, success: bool, user=None, reason: str = ''):
        action = (AuthEvent.ACTION_LOGIN_SUCCESS if success
                  else AuthEvent.ACTION_LOGIN_FAIL)
        audit_log_auth(user, action, request, reason=reason)

    @extend_schema(
        summary='Login — obtener par de tokens JWT',
        description=(
            'FR-AUTH-02.01: rate limiting 5 intentos / 15 min por IP. '
            'FR-AUTH-02.15: objeto user incluido en la respuesta. '
            'Emite AuthEvent LOGIN_SUCCESS / LOGIN_FAIL.'
        ),
        responses={
            200: OpenApiResponse(description='Access + refresh tokens con objeto user.'),
            401: OpenApiResponse(description='Credenciales inválidas o email no verificado.'),
            429: OpenApiResponse(description='Rate limit — demasiados intentos fallidos.'),
        },
        tags=['auth'],
    )
    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)

        # FR-AUTH-02.01: verificar bloqueo ANTES de validar credenciales
        seconds_remaining = check_login_rate_limit(ip)
        if seconds_remaining:
            self._audit_login(request, success=False,
                              reason=AuthEvent.REASON_RATE_LIMITED)
            response = Response(
                {
                    'detail': 'Demasiados intentos fallidos. Intenta de nuevo más tarde.',
                    'retry_after': seconds_remaining,
                },
                status=429,
            )
            response['Retry-After'] = str(seconds_remaining)
            return response

        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed as exc:
            # super().post() puede lanzar AuthenticationFailed (APIException)
            # que no convierte a Response dentro de post() — sube a dispatch().
            # Registramos el fallo antes de dejar que suba.
            record_failed_attempt(ip)
            reason = AuthEvent.REASON_BAD_CREDS
            detail = getattr(exc, 'detail', None)
            if isinstance(detail, dict) and detail.get('codigo_error') == 'EMAIL_NOT_VERIFIED':
                reason = AuthEvent.REASON_EMAIL_NOT_VERIFIED
            self._audit_login(request, success=False, reason=reason)
            raise

        if response.status_code == 200:
            # FR-AUTH-02.14: login exitoso — limpiar contador
            reset_failed_attempts(ip)
            # D-10 audit log: usuario resuelto via response data.
            user_id = (response.data or {}).get('user', {}).get('id')
            user = User.objects.filter(pk=user_id).first() if user_id else None
            self._audit_login(request, success=True, user=user)
            # ADR-018 (DEC-STF-AUTH-COOKIE): ademas del JWT, se establece la
            # sesion de servidor. SessionMiddleware pone la cookie HttpOnly, de
            # modo que la sesion sobrevive a recargas de pagina (el token en
            # memoria del SPA se pierde, la cookie no). Aditivo: no altera la
            # respuesta JWT existente. El backend se pasa explicito porque el
            # user se autentico via el serializer de SimpleJWT, no via un
            # backend de django.contrib.auth.
            if user is not None:
                django_login(
                    request, user,
                    backend='django.contrib.auth.backends.ModelBackend',
                )
                # UC-AUTH-17 (H-16): registra la sesion (IP/dispositivo).
                record_user_session(request, user)
        elif response.status_code in (400, 401):
            record_failed_attempt(ip)
            self._audit_login(request, success=False,
                              reason=AuthEvent.REASON_BAD_CREDS)

        return response


# ─── Refresh con validacion is_active (D-26) ──────────────────────────────────


class PYTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Extiende ``TokenRefreshSerializer`` simplejwt para validar
    ``user.is_active`` antes de emitir nuevo access. Cierra D-26
    del audit T-102 (privilege-after-suspend window).

    Si el usuario fue suspendido (UC-AUTH-13) o auto-baja
    (UC-AUTH-16) tras emitir el refresh, esta validacion lo
    rechaza con 401 + ``codigo_error='ACCOUNT_INACTIVE'`` y
    blacklistea el refresh (anti-replay).

    Ver DEC-REF-1 (subclass pattern), DEC-REF-2 (blacklist),
    DEC-REF-3 (401 + ACCOUNT_INACTIVE), DEC-REF-4 (lookup
    defensivo con .filter().first()).
    """

    def validate(self, attrs):
        # IMPORTANTE: el lookup del user va ANTES de super().validate()
        # porque super() rota el refresh (BLACKLIST_AFTER_ROTATION=True);
        # tras super(), attrs['refresh'] esta blacklisteado y cualquier
        # re-instanciacion de RefreshToken fallaria por check_blacklist.
        #
        # RefreshToken(token) verifica firma + expiracion + blacklist
        # check pero NO blacklistea por si mismo.
        request = self.context.get('request') if hasattr(self, 'context') else None
        refresh = RefreshToken(attrs['refresh'])
        user_id = refresh.get(jwt_settings.USER_ID_CLAIM)
        user = User.objects.filter(pk=user_id).first()

        if not user or not user.is_active:
            # Anti-replay: blacklistear antes de raise.
            try:
                refresh.blacklist()
            except Exception:
                # silent OK because blacklist puede fallar si el token
                # ya esta en blacklist (idempotente). Aceptable.
                pass
            # D-25 audit log: refresh fallido por user inactivo.
            audit_log_auth(
                user, AuthEvent.ACTION_REFRESH_FAIL, request,
                reason=AuthEvent.REASON_ACCOUNT_INACTIVE,
            )
            raise InvalidToken({
                'detail': 'Cuenta inactiva. Inicia sesion de nuevo.',
                'codigo_error': 'ACCOUNT_INACTIVE',
            })

        # User valido y activo: dejar simplejwt rotar + emitir
        # nuevo access (+ nuevo refresh por ROTATE_REFRESH_TOKENS).
        data = super().validate(attrs)
        # D-25 audit log: refresh exitoso.
        audit_log_auth(
            user, AuthEvent.ACTION_REFRESH_SUCCESS, request,
        )
        return data


class PYTokenRefreshView(TokenRefreshView):
    """View custom que usa ``PYTokenRefreshSerializer``."""
    serializer_class = PYTokenRefreshSerializer


# ─── Logout audit (D-19) ───────────────────────────────────────────────────


class PYTokenBlacklistView(TokenBlacklistView):
    """
    Subclase de TokenBlacklistView que emite AuthEvent.ACTION_LOGOUT
    tras el blacklist exitoso del refresh. D-19 del audit T-102.
    """
    @extend_schema(
        summary='Logout — blacklistear refresh token',
        description='D-19: emite AuthEvent.ACTION_LOGOUT tras blacklist exitoso.',
        responses={
            200: OpenApiResponse(description='Refresh token invalidado.'),
            400: OpenApiResponse(description='Token inválido o ya blacklisteado.'),
            401: OpenApiResponse(description='No autenticado.'),
        },
        tags=['auth'],
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if 200 <= response.status_code < 300:
            # User puede ser anon si la request no traia Authorization;
            # logout suele ser anon en simplejwt (solo blacklistea token).
            user = request.user if request.user.is_authenticated else None
            audit_log_auth(user, AuthEvent.ACTION_LOGOUT, request)
        return response
