"""
tokens_email.py — apps.modules.users

Generacion y validacion de tokens HMAC para:
- Recuperacion de contrasena (UC-AUTH-09)
- Verificacion de email (UC-AUTH-10)

El token en claro se envia por email.
Solo el hash SHA-256 se guarda en la BD.
"""
import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import quote
from django.contrib.sessions.models import Session
from django.core.cache import cache
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from apps.core.email_executor import dispatch_email
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from .models import PasswordResetToken, EmailVerificationToken


logger = logging.getLogger(__name__)


RESET_TTL_HOURS  = 1
VERIFY_TTL_HOURS = 24


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


# ─── Password Reset ──────────────────────────────────────────────────────

def check_rate_limit(email: str, max_requests: int = 3, window: int = 3600) -> bool:
    """
    Retorna True si se puede proceder (dentro del limite).
    Retorna False si se supero el limite.
    """
    key = f'pw_reset:{hashlib.sha256(email.lower().encode()).hexdigest()}'
    count = cache.get(key, 0)
    if count >= max_requests:
        return False
    cache.set(key, count + 1, timeout=window)
    return True


def create_password_reset_token(user) -> str:
    """
    Genera un token de recuperacion, lo persiste y retorna el token en claro.
    """
    plain = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(plain),
        expires_at=timezone.now() + timedelta(hours=RESET_TTL_HOURS),
    )
    return plain


def send_password_reset_email(user, plain_token: str):
    reset_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')}/auth/reset-password/?token={plain_token}"
    nombre = user.first_name or user.email
    html_body = render_to_string('emails/reset_password.html', {
        'nombre': nombre,
        'reset_url': reset_url,
        'ttl_hours': RESET_TTL_HOURS,
    })
    dispatch_email(
        subject='Recupera tu contrasena — PracticaYoruba',
        message=(
            f'Hola {nombre},\n\n'
            f'Recibimos una solicitud para recuperar la contrasena de tu cuenta.\n'
            f'Sigue este enlace (valido por {RESET_TTL_HOURS} hora):\n\n'
            f'{reset_url}\n\n'
            f'Si no solicitaste esto, ignora este mensaje.\n\n'
            f'— Equipo PracticaYoruba'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.com'),
        recipient_list=[user.email],
        html_message=html_body,
    )


def validate_password_reset_token(plain: str):
    """
    Valida el token. Retorna el PasswordResetToken si es valido.
    Lanza ValueError si es invalido, expirado o ya usado.
    """
    token_hash = _hash_token(plain)
    try:
        obj = PasswordResetToken.objects.get(
            token_hash=token_hash,
            used_at__isnull=True,
        )
    except PasswordResetToken.DoesNotExist:
        raise ValueError('Token invalido o ya utilizado.')
    if obj.expires_at < timezone.now():
        raise ValueError('El enlace de recuperacion ha expirado.')
    return obj


def invalidate_all_sessions(user, keep_session_key=None):
    """Cierra las sesiones activas del usuario (logout-all / baja / cambio pass).

    Tras la migracion a sesion de servidor (ADR-018), la auth del web vive en
    ``django_session``, no en tokens JWT. Para forzar re-login hay que **borrar
    las filas de sesion** del usuario, no solo blacklistear refresh tokens.

    ``keep_session_key`` preserva **la sesion en curso** (CR-3): en cambio de
    contrasena, quien lo ejecuta debe conservar su propia sesion (patron nativo
    ``update_session_auth_hash``), no auto-desloguearse. En reset / logout-all /
    self-delete se pasa ``None`` y se borran todas.

    Django no indexa ``django_session`` por usuario, asi que se recorren las
    sesiones no expiradas y se borran las cuyo ``_auth_user_id`` coincide. La
    tabla la mantiene acotada ``clearsessions`` (cron), por lo que el recorrido
    es sobre sesiones vivas.

    Se conserva el blacklist de refresh tokens JWT (dormidos hoy; utiles si en
    el futuro se re-habilita JWT para movil): asi la baja tambien invalida
    cualquier token emitido antes de la migracion o por un cliente movil.
    """
    # 1) Sesiones de servidor (auth web actual).
    uid = str(user.pk)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if keep_session_key and session.session_key == keep_session_key:
            continue  # CR-3: preservar la sesion del request en curso.
        try:
            if session.get_decoded().get('_auth_user_id') == uid:
                session.delete()
        except Exception:
            # Loud-log (no re-raise): una sesion corrupta no debe frenar el
            # borrado del resto. DEC-DOC-008.
            logger.warning(
                'session decode/delete failed user_id=%s session_key=%s',
                user.pk, session.session_key, exc_info=True,
            )

    # 2) Refresh tokens JWT (dormidos; back-compat / movil futuro). CR-4: se
    # excluyen los que ya estan en blacklist (rotacion previa con
    # ROTATE_REFRESH_TOKENS): re-blacklistearlos lanza TokenError y ensuciaba
    # el log con un traceback por token en cada invocacion.
    already_black = set(
        BlacklistedToken.objects.filter(token__user=user)
        .values_list('token_id', flat=True)
    )
    for token in OutstandingToken.objects.filter(user=user).exclude(id__in=already_black):
        try:
            RefreshToken(token.token).blacklist()
        except TokenError:
            # silent OK because el token expiro o quedo invalido entre el
            # filtro y el blacklist (carrera benigna); no hay nada que
            # invalidar. DEC-DOC-008.
            continue


# ─── Email Verification ───────────────────────────────────────────────────

def create_verification_token(user) -> str:
    """
    Genera un token de verificacion de email y lo persiste.
    Retorna el token en claro.
    """
    plain = secrets.token_urlsafe(32)
    EmailVerificationToken.objects.create(
        user=user,
        token_hash=_hash_token(plain),
        expires_at=timezone.now() + timedelta(hours=VERIFY_TTL_HOURS),
    )
    return plain


def _safe_internal_path(raw) -> str:
    """Guard anti open-redirect (equivalente a is_safe_url): solo rutas
    internas (un solo '/', sin '//', ':' ni backslash)."""
    if not isinstance(raw, str) or not raw.startswith('/'):
        return ''
    if raw.startswith('//') or ':' in raw or '\\' in raw:
        return ''
    return raw


def send_verification_email(user, plain_token: str, next_path: str = ''):
    verify_url = (
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')}"
        f"/auth/verify-email?token={plain_token}"
    )
    safe_next = _safe_internal_path(next_path)
    if safe_next:
        verify_url += f"&next={quote(safe_next, safe='/')}"
    nombre = user.first_name or user.email
    html_body = render_to_string('emails/verify_account.html', {
        'nombre': nombre,
        'verify_url': verify_url,
        'ttl_hours': VERIFY_TTL_HOURS,
    })
    dispatch_email(
        subject='Activa tu cuenta — PracticaYoruba',
        message=(
            f'Hola {nombre},\n\n'
            f'Activa tu cuenta siguiendo este enlace (valido por {VERIFY_TTL_HOURS} horas):\n\n'
            f'{verify_url}\n\n'
            f'Si no te registraste en PracticaYoruba, ignora este mensaje.\n\n'
            f'— Equipo PracticaYoruba'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.com'),
        recipient_list=[user.email],
        html_message=html_body,
    )


def _token_error(code: str, message: str) -> ValueError:
    e = ValueError(message)
    e.error_code = code  # type: ignore[attr-defined]
    return e


def validate_verification_token(plain: str):
    """
    Valida el token de verificacion de email — **single-use estricto**.
    Retorna el EmailVerificationToken si es valido y sin usar.
    Lanza ValueError (con .error_code) si es invalido, ya usado o expirado.

    Postmortem verify-token-reuso (2026-07-01): el orden de las comprobaciones
    ponia ``is_active`` ANTES de ``used_at``, asi que el 2o clic caia en la rama
    idempotente ("ya activa" -> exito) en vez de "enlace ya utilizado" — a
    diferencia del reset de contrasena, que si es single-use. Se reordena para
    evaluar ``used_at`` (y expiracion) PRIMERO, alineando la semantica con el
    reset: un enlace ya consumido devuelve ``TOKEN_ALREADY_USED``.
    """
    token_hash = _hash_token(plain)
    try:
        obj = EmailVerificationToken.objects.get(token_hash=token_hash)
    except EmailVerificationToken.DoesNotExist:
        raise _token_error('TOKEN_INVALID', 'Token de verificacion invalido.')
    if obj.used_at is not None:
        # Single-use: un enlace ya usado no se reutiliza (2o clic incluido).
        raise _token_error(
            'TOKEN_ALREADY_USED',
            'Este enlace ya fue utilizado. Si tu cuenta ya esta activa, inicia sesion.',
        )
    if obj.expires_at < timezone.now():
        raise _token_error('TOKEN_EXPIRED', 'El enlace de verificacion ha expirado. Solicita uno nuevo.')
    if obj.user.is_active:
        # Token sin usar pero cuenta ya activa (p.ej. activada por otra via):
        # idempotente, no hay nada que activar.
        return None
    return obj
