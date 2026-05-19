"""
tokens_email.py — apps.users

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

from django.core.cache import cache

logger = logging.getLogger(__name__)
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import PasswordResetToken, EmailVerificationToken

RESET_TTL_HOURS  = 1
VERIFY_TTL_HOURS = 24


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


# ─── Password Reset ──────────────────────────────────────────────────

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
    send_mail(
        subject='Recupera tu contrasena — PracticaYoruba',
        message=(
            f'Hola {user.first_name or user.username},\n\n'
            f'Recibimos una solicitud para recuperar la contrasena de tu cuenta.\n'
            f'Sigue este enlace (valido por {RESET_TTL_HOURS} hora):\n\n'
            f'{reset_url}\n\n'
            f'Si no solicitaste esto, ignora este mensaje.\n\n'
            f'— Equipo PracticaYoruba'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx'),
        recipient_list=[user.email],
        fail_silently=True,
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


def invalidate_all_sessions(user):
    """
    DT-S2-03: invalida todos los refresh tokens activos del usuario.
    """
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    from rest_framework_simplejwt.tokens import RefreshToken
    for token in OutstandingToken.objects.filter(user=user):
        try:
            RefreshToken(token.token).blacklist()
        except Exception:
            # Loud-log (no re-raise): el loop debe seguir invalidando
            # el resto de tokens aunque uno este corrupto/duplicado.
            # DEC-DOC-008.
            logger.warning(
                'blacklist refresh token failed user_id=%s token_id=%s',
                user.pk, token.id, exc_info=True,
            )


# ─── Email Verification ───────────────────────────────────────────────

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


def send_verification_email(user, plain_token: str):
    verify_url = (
        f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')}"
        f"/verificar-email/?token={plain_token}"
    )
    send_mail(
        subject='Activa tu cuenta — PracticaYoruba',
        message=(
            f'Hola {user.first_name or user.username},\n\n'
            f'Activa tu cuenta siguiendo este enlace (valido por {VERIFY_TTL_HOURS} horas):\n\n'
            f'{verify_url}\n\n'
            f'Si no te registraste en PracticaYoruba, ignora este mensaje.\n\n'
            f'— Equipo PracticaYoruba'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx'),
        recipient_list=[user.email],
        fail_silently=True,
    )


def validate_verification_token(plain: str):
    """
    Valida el token de verificacion de email.
    Retorna el EmailVerificationToken si es valido.
    Lanza ValueError si es invalido o expirado.
    Si la cuenta ya esta activa, retorna None (idempotente).
    """
    token_hash = _hash_token(plain)
    try:
        obj = EmailVerificationToken.objects.get(token_hash=token_hash)
    except EmailVerificationToken.DoesNotExist:
        raise ValueError('Token de verificacion invalido.')
    if obj.user.is_active:
        return None  # idempotente — ya estaba activa
    if obj.used_at is not None:
        return None  # ya usada pero cuenta activa
    if obj.expires_at < timezone.now():
        raise ValueError('El enlace de verificacion ha expirado. Solicita uno nuevo.')
    return obj
