"""Servicios TOTP — addons.authz_totp (DEC-01, ~ auth_totp de Odoo).

Adaptado de ``auth_totp/models/res_users.py`` (``_totp_check`` / ``_totp_try_setting``)
y del wizard (``auth_totp_wizard.py``, generación del secreto + URI de
aprovisionamiento). La verificación usa ``TOTP.match`` verbatim de Odoo: compara
``hotp(key, counter) == code`` con ``code`` como ``int`` (maneja ceros a la
izquierda: ``hotp`` devuelve el entero, ``int('012345') == 12345``).
"""
import base64
import os
from urllib.parse import quote, urlencode

from addons.base.models import SystemParameter
from addons.authz_totp.models import TotpSecret
from addons.authz_totp.totp import ALGORITHM, DIGITS, TIMESTEP, TOTP, TOTP_SECRET_SIZE

# Marca mostrada en la app authenticator. NADA cableado: L2, sembrado por la
# migración (0001) a 'Kaupamex' (marca de plataforma L0), editable en caliente.
PARAM_ISSUER = 'authz.totp_issuer'


def _issuer():
    return str(SystemParameter.get_param(PARAM_ISSUER, 'Kaupamex'))


def generate_secret():
    """Secreto base32 de 160 bits (RFC 4226 R6, como Odoo ``TOTP_SECRET_SIZE``)."""
    return base64.b32encode(os.urandom(TOTP_SECRET_SIZE // 8)).decode('ascii')


def provisioning_uri(email, secret):
    """URI ``otpauth://`` para el QR (Key-Uri-Format de Google Authenticator)."""
    issuer = _issuer()
    label = quote(f'{issuer}:{email}')
    params = urlencode({
        'secret': secret,
        'issuer': issuer,
        'algorithm': ALGORITHM.upper(),
        'digits': DIGITS,
        'period': TIMESTEP,
    })
    return f'otpauth://totp/{label}?{params}'


def _code_matches(secret, code):
    """True si ``code`` (str de 6 dígitos) casa el secreto base32 ahora."""
    code = str(code or '').strip()
    if not code.isdigit():
        return False
    key = base64.b32decode(secret)
    return TOTP(key).match(int(code)) is not None


def totp_enabled(user):
    """True si el usuario tiene 2FA TOTP activo (secreto confirmado)."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return False
    return TotpSecret.objects.filter(user_id=user.pk, confirmed=True).exists()


def verify_code(user, code):
    """Verifica ``code`` contra el secreto confirmado del usuario (login 2FA)."""
    row = TotpSecret.objects.filter(user_id=user.pk, confirmed=True).first()
    if row is None:
        return False
    return _code_matches(row.secret, code)


def begin_setup(user):
    """Inicia el alta de 2FA: genera un secreto PENDIENTE y devuelve
    ``(secret, provisioning_uri)``. Rechaza si ya hay 2FA activo."""
    if totp_enabled(user):
        return None
    secret = generate_secret()
    TotpSecret.objects.update_or_create(
        user_id=user.pk, defaults={'secret': secret, 'confirmed': False},
    )
    return secret, provisioning_uri(user.email, secret)


def confirm_setup(user, code):
    """Activa el 2FA si ``code`` casa el secreto pendiente. Devuelve bool."""
    row = TotpSecret.objects.filter(user_id=user.pk, confirmed=False).first()
    if row is None:
        return False
    if not _code_matches(row.secret, code):
        return False
    row.confirmed = True
    row.save(update_fields=['confirmed', 'updated_at'])
    return True


def disable(user, code):
    """Desactiva el 2FA si ``code`` es válido (confirma identidad). Devuelve bool."""
    row = TotpSecret.objects.filter(user_id=user.pk, confirmed=True).first()
    if row is None:
        return False
    if not _code_matches(row.secret, code):
        return False
    row.delete()
    return True
