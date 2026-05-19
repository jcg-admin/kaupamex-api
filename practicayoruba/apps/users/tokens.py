"""
tokens.py — apps.users

PYTokenObtainPairView: login personalizado con:
  FR-AUTH-02.01: rate limiting por IP (max 5 intentos fallidos / 15 min)
  FR-AUTH-02.07: normalización del identificador a minúsculas
  FR-AUTH-02.09: mensaje diferenciado para email no verificado
  FR-AUTH-02.14: restablecimiento del contador tras login exitoso
  FR-AUTH-02.15: objeto 'user' en la respuesta
"""
import hashlib
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import AuthenticationFailed

User = get_user_model()

# ─── Constantes de rate limiting ──────────────────────────────────────
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
            user = User.objects.get(username__iexact=username)
            if not user.is_active and user.has_usable_password():
                raise AuthenticationFailed(
                    detail={
                        'codigo': 'EMAIL_NO_VERIFICADO',
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

        # FR-AUTH-02.15 — añadir objeto user a la respuesta
        user = self.user
        data['user'] = {
            'id':         user.pk,
            'username':   user.username,
            'email':      user.email,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'is_staff':   user.is_staff,
            'avatar_url': user.get_avatar_url(),
        }
        return data


class PYTokenObtainPairView(TokenObtainPairView):
    """
    View de login con rate limiting por IP (FR-AUTH-02.01 / FR-AUTH-02.14).
    """
    serializer_class = PYTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)

        # FR-AUTH-02.01: verificar bloqueo ANTES de validar credenciales
        seconds_remaining = check_login_rate_limit(ip)
        if seconds_remaining:
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
        except Exception:
            # super().post() puede lanzar AuthenticationFailed (APIException)
            # que no convierte a Response dentro de post() — sube a dispatch().
            # Registramos el fallo antes de dejar que suba.
            record_failed_attempt(ip)
            raise

        if response.status_code == 200:
            # FR-AUTH-02.14: login exitoso — limpiar contador
            reset_failed_attempts(ip)
        elif response.status_code in (400, 401):
            record_failed_attempt(ip)

        return response
