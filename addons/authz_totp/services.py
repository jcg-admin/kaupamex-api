"""Servicios TOTP — addons.authz_totp (DEC-01, ~ auth_totp de Odoo).

Adaptado de ``auth_totp/models/res_users.py`` (``_totp_check`` / ``_totp_try_setting``)
y del wizard (``auth_totp_wizard.py``, generación del secreto + URI de
aprovisionamiento). La verificación usa ``TOTP.match`` verbatim de Odoo: compara
``hotp(key, counter) == code`` con ``code`` como ``int`` (maneja ceros a la
izquierda: ``hotp`` devuelve el entero, ``int('012345') == 12345``).
"""
import base64
import hashlib
import logging
import os
import secrets
from urllib.parse import quote, urlencode

from django.utils import timezone

from addons.base.models import SystemParameter
from addons.authz_totp.models import TotpRecoveryCode, TotpSecret
from addons.authz_totp.models.totp import ALGORITHM, DIGITS, TIMESTEP, TOTP, TOTP_SECRET_SIZE

_logger = logging.getLogger(__name__)

# Marca mostrada en la app authenticator. NADA cableado: L2, sembrado por la
# migración (0001) a 'Kaupamex' (marca de plataforma L0), editable en caliente.
PARAM_ISSUER = 'authz.totp_issuer'
# Cantidad de códigos de recuperación por alta. NADA cableado: L2, sembrado por
# la migración (0002) a '10' (default de Odoo auth_totp), editable en caliente.
PARAM_RECOVERY_COUNT = 'authz.totp_recovery_codes'


def _issuer():
    return str(SystemParameter.get_param(PARAM_ISSUER, 'Kaupamex'))


def _recovery_count():
    """Nº de códigos de recuperación a generar (L2, fallback 10 = default Odoo)."""
    try:
        n = int(SystemParameter.get_param(PARAM_RECOVERY_COUNT, '10'))
    except (TypeError, ValueError):
        n = 10
    return max(1, n)


def _hash_recovery(code):
    """SHA-256 hex del código normalizado (sin espacios/guiones, minúsculas)."""
    norm = ''.join(str(code or '').split()).replace('-', '').lower()
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()


def generate_recovery_codes(user):
    """Regenera los códigos de recuperación del usuario. Devuelve la lista de
    códigos EN CLARO (sólo se muestran aquí; en BD se guardan hasheados)."""
    TotpRecoveryCode.objects.filter(user_id=user.pk).delete()
    codes = []
    for _ in range(_recovery_count()):
        # 10 hex chars agrupados 'xxxxx-xxxxx' (fácil de leer/teclear).
        raw = secrets.token_hex(5)
        codes.append(f'{raw[:5]}-{raw[5:]}')
    TotpRecoveryCode.objects.bulk_create([
        TotpRecoveryCode(user_id=user.pk, code_hash=_hash_recovery(c))
        for c in codes
    ])
    return codes


def count_recovery_codes(user):
    """Nº de códigos de recuperación aún válidos (no consumidos) del usuario."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return 0
    return TotpRecoveryCode.objects.filter(
        user_id=user.pk, used_at__isnull=True,
    ).count()


def consume_recovery_code(user, code):
    """Consume un código de recuperación válido (un solo uso). Devuelve bool.

    Sólo aplica a usuarios con 2FA activo; un código consumido no vuelve a
    servir. La comparación es por hash (el plano no se guarda)."""
    if not totp_enabled(user):
        return False
    norm = ''.join(str(code or '').split()).replace('-', '')
    if not norm:
        return False
    row = TotpRecoveryCode.objects.filter(
        user_id=user.pk, code_hash=_hash_recovery(code), used_at__isnull=True,
    ).first()
    if row is None:
        return False
    row.used_at = timezone.now()
    row.save(update_fields=['used_at', 'updated_at'])
    return True


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


def _matching_counter(secret, code):
    """El intervalo en que ``code`` casa el secreto base32, o ``None``.

    ≙ ``TOTP(key).match(credentials['token'])`` (``odoo19c:
    auth_totp/models/res_users.py:79``). Devuelve el **contador**, no un
    booleano: es el dato con el que la fuente impide reusar un código, y
    colapsarlo a ``bool`` es lo que dejaba abierta la ventana entera.

    ``match`` recorre ``[t-window, t+window]`` con ``window = TIMESTEP``, así
    que un mismo código casa durante ~90 s. Sin el contador no hay forma de
    distinguir *"otro código del mismo minuto"* de *"el mismo código otra vez"*.
    """
    code = str(code or '').strip()
    if not code.isdigit():
        return None
    key = base64.b32decode(secret)
    return TOTP(key).match(int(code))


def totp_enabled(user):
    """True si el usuario tiene 2FA TOTP activo (secreto confirmado)."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return False
    return TotpSecret.objects.filter(user_id=user.pk, confirmed=True).exists()


def verify_code(user, code):
    """Verifica ``code`` contra el secreto confirmado del usuario (login 2FA).

    ≙ la rama ``type == 'totp'`` de ``_check_credentials`` (``odoo19c:
    auth_totp/models/res_users.py:76-92``), incluida su **segunda** guarda: un
    código ya usado no vale una segunda vez.

    Sin ella la ventana de ``match`` —±30 s alrededor del intervalo actual—
    convierte cada código en un pase reutilizable durante ~90 s. Quien lo vea
    de reojo, lo lea de un registro o lo intercepte, entra con él.

    La fuente distingue los dos rechazos en el registro (``FAIL`` contra
    ``REUSE``) y **no** al llamador: los dos son la misma negativa hacia fuera,
    porque decir cuál fue le confirmaría al atacante que el código era bueno.
    """
    row = TotpSecret.objects.filter(user_id=user.pk, confirmed=True).first()
    if row is None:
        return False
    counter = _matching_counter(row.secret, code)
    if counter is None:
        _logger.info('2FA check: FAIL for %r', user.login)
        return False
    if row.last_counter is not None and counter <= row.last_counter:
        _logger.warning('2FA check: REUSE for %r', user.login)
        return False
    row.last_counter = counter
    row.save(update_fields=['last_counter', 'updated_at'])
    _logger.info('2FA check: SUCCESS for %r', user.login)
    return True


def begin_setup(user):
    """Inicia el alta de 2FA: genera un secreto PENDIENTE y devuelve
    ``(secret, provisioning_uri)``. Rechaza si ya hay 2FA activo."""
    if totp_enabled(user):
        return None
    secret = generate_secret()
    # ≙ ``_inverse_token`` (``:227-228``), que pone ``totp_last_counter = False``
    # al cambiar el secreto: el contador es del secreto viejo y con otro secreto
    # no significa nada. Sin este reinicio, un alta nueva heredaría el umbral de
    # la anterior y rechazaría códigos legítimos hasta alcanzarlo.
    TotpSecret.objects.update_or_create(
        user_id=user.pk,
        defaults={'secret': secret, 'confirmed': False, 'last_counter': None},
    )
    return secret, provisioning_uri(user.email, secret)


def confirm_setup(user, code):
    """Activa el 2FA si ``code`` casa el secreto pendiente.

    Devuelve la lista de códigos de recuperación EN CLARO en caso de éxito
    (se muestran una sola vez, como Odoo), o ``None`` si el código es inválido
    o no hay alta pendiente.

    Asienta el contador del código de alta — ≙ ``self.sudo().totp_last_counter
    = match`` de ``_totp_try_setting`` (``:110``). No es contabilidad: es lo que
    impide que el **mismo** código que acaba de activar el 2FA sirva además
    para el primer login, que ocurre segundos después y cae en la misma
    ventana."""
    row = TotpSecret.objects.filter(user_id=user.pk, confirmed=False).first()
    if row is None:
        return None
    counter = _matching_counter(row.secret, code)
    if counter is None:
        return None
    row.confirmed = True
    row.last_counter = counter
    row.save(update_fields=['confirmed', 'last_counter', 'updated_at'])
    return generate_recovery_codes(user)


def disable(user, code):
    """Desactiva el 2FA si ``code`` es válido (confirma identidad). Devuelve bool.

    Acepta un código TOTP actual **o** un código de recuperación válido — así un
    usuario que perdió el authenticator todavía puede apagar el 2FA. Borra el
    secreto y todos los códigos de recuperación."""
    row = TotpSecret.objects.filter(user_id=user.pk, confirmed=True).first()
    if row is None:
        return False
    counter = _matching_counter(row.secret, code)
    reused = counter is not None and row.last_counter is not None and counter <= row.last_counter
    if (counter is None or reused) and not consume_recovery_code(user, code):
        return False
    row.delete()
    TotpRecoveryCode.objects.filter(user_id=user.pk).delete()
    return True
