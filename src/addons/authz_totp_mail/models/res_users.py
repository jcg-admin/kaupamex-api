"""2FA por correo — clave, código, envío, verificación, política e invitación.

Adaptación fiel de Odoo ``auth_totp_mail/models/res_users.py`` (LGPL-3,
216 loc, leído completo). La referencia extiende ``res.users``; aquí son
funciones sobre el usuario (no hay ``_inherit``), mismo criterio que
``authz_ldap.models.res_users``.

Métodos de la referencia → aquí:

- ``_get_totp_mail_key`` / ``_get_totp_mail_code`` / ``_send_totp_mail_code``
  / ``_check_credentials`` (type ``totp_mail``) → ``totp_mail_key`` /
  ``totp_mail_code`` / ``send_totp_mail_code`` / ``verify_totp_mail_code``.
- ``_mfa_type`` (política ``auth_totp.policy``) → ``totp_mail_required``.
- ``action_totp_invite`` / ``get_totp_invite_url`` → ``invite_users`` /
  ``get_totp_invite_url`` (la URL es config L2: el puente de portal la
  re-enruta por audiencia, como hace ``auth_totp_portal`` en la referencia).
- ``write`` (notificación al activar/desactivar 2FA) → ``../signals.py``.
- ``authenticate`` + ``_notify_security_new_connection`` → NO portados:
  dependen de ``auth_totp.device`` (dispositivo de confianza por cookie
  ``td_id``), modelo no portado — gap nombrado en H-API-232.
- ``_rpc_api_keys_only`` / ``action_open_my_account_settings`` → NO
  portados: RPC keys y acción de ventana del backoffice Odoo.

**Rate limit (divergencia declarada):** la referencia llama
``_totp_rate_limit('code_check'|'send_email')`` de ``auth_totp``, que
persiste en ``auth_totp_rate_limit_log`` — modelo NO portado (mismo gap).
Hasta portarlo, estos flujos quedan sin rate limit propio.
"""
import logging
from datetime import datetime

from django.apps import apps as django_apps

from exceptions import AccessDenied, UserError
from tools.misc import hmac as tools_hmac

from addons.authz_totp.models.totp import TOTP, hotp
from addons.base.models import SystemParameter
from addons.mail.models.email_executor import dispatch_email
from addons.mail.models.mail_template import MailTemplate

_logger = logging.getLogger(__name__)

# ≙ ir.config_parameter 'auth_totp.policy' (res_users.py:121-126):
# '' (apagada) | 'all_required' | 'employee_required'.
PARAM_TOTP_POLICY = 'authz_totp.policy'
# URL a la que invita el correo. En la referencia es la acción del
# backoffice ('/odoo/action-...', res_users.py:93-94) y el puente
# auth_totp_portal la re-enruta a '/my/security' para no-internos. Aquí es
# L2 para que cada despliegue apunte a su ruta del SPA.
PARAM_INVITE_URL = 'authz_totp_mail.invite_url'

# Ventana del código por correo: 1 hora, igual que la referencia
# (window=3600, timestep=3600 — res_users.py:146,177).
TOTP_MAIL_WINDOW = 3600
TOTP_MAIL_TIMESTEP = 3600

TEMPLATE_TOTP_INVITE = 'authz_totp_mail: invitación 2FA'
TEMPLATE_TOTP_MAIL_CODE = 'authz_totp_mail: código 2FA'


def totp_mail_key(user):
    """≙ ``_get_totp_mail_key`` (res_users.py:160-162): clave HMAC derivada
    del secreto del despliegue + identidad y último login del usuario (el
    ``login_date`` de la referencia invalida los códigos al re-loguear)."""
    message = str((user.id, user.login, user.last_login))
    return tools_hmac('auth_totp_mail-code', message).encode()


def totp_mail_code(user):
    """≙ ``_get_totp_mail_code`` (res_users.py:164-182): ``(code, segundos)``.

    El guard de sesión pre-auth de la referencia (``request.session.pre_uid``)
    pertenece a su flujo de login web; aquí el llamador controla el contexto.
    """
    key = totp_mail_key(user)
    counter = int(datetime.now().timestamp() / TOTP_MAIL_TIMESTEP)
    code = hotp(key, counter)
    return str(code).zfill(6), TOTP_MAIL_WINDOW


def verify_totp_mail_code(user, code):
    """≙ ``_check_credentials`` type ``totp_mail`` (res_users.py:139-158).

    Devuelve True si el código de 6 dígitos coincide dentro de la ventana.
    Levanta ``AccessDenied`` con el mismo mensaje que la referencia si no.
    """
    try:
        token = int(code)
    except (TypeError, ValueError):
        token = None
    match = None
    if token is not None:
        match = TOTP(totp_mail_key(user)).match(
            token, window=TOTP_MAIL_WINDOW, timestep=TOTP_MAIL_TIMESTEP)
    if match is None:
        _logger.info('2FA check (mail): FAIL for %r', user.login)
        raise AccessDenied(
            'Verification failed, please double-check the 6-digit code')
    _logger.info('2FA check (mail): SUCCESS for %r', user.login)
    return True


def send_totp_mail_code(user):
    """≙ ``_send_totp_mail_code`` (res_users.py:184-216): renderiza la
    plantilla del código y la despacha al email del usuario."""
    if not user.login:
        raise UserError(
            'Cannot send email: user %s has no email address.' % user)
    code, expiration = totp_mail_code(user)
    template = MailTemplate.objects.filter(
        name=TEMPLATE_TOTP_MAIL_CODE).first()
    if template is None:
        raise UserError('TOTP mail template is not seeded.')
    rendered = template.render(user, extra_context={
        'code': code, 'expiration_minutes': expiration // 60,
    })
    dispatch_email(
        rendered['subject'], rendered['body_html'],
        rendered['email_from'] or None, [user.login])
    _logger.info('TOTP mail code sent to %r', user.login)


def totp_mail_required(user):
    """≙ el tramo de política de ``_mfa_type`` (res_users.py:118-128):
    True si la política L2 exige 2FA a este usuario y no tiene TOTP de app
    activo (el fallback por correo aplica entonces).

    ``employee_required`` (≙ ``_is_internal`` de la referencia) usa
    ``ResUsers.is_internal()`` — el eje interno/portal real, resuelto por el
    ``user_type`` de los grupos (antes era el proxy ``partner.employee``).
    """
    TotpSecret = django_apps.get_model('authz_totp', 'TotpSecret')
    if TotpSecret.objects.filter(user=user, confirmed=True).exists():
        return False  # ya tiene mfa de app; el de correo es el fallback
    policy = SystemParameter.get_param(PARAM_TOTP_POLICY, '')
    if policy == 'all_required':
        return True
    if policy == 'employee_required':
        return user.is_internal()
    return False


def get_totp_invite_url():
    """≙ ``get_totp_invite_url`` (res_users.py:93-94), como config L2."""
    return str(SystemParameter.get_param(
        PARAM_INVITE_URL, '/account/security'))


def invite_users(users, inviter):
    """≙ ``action_totp_invite`` (res_users.py:96-116): envía la invitación a
    los usuarios que aún no tienen 2FA activo y devuelve sus nombres."""
    TotpSecret = django_apps.get_model('authz_totp', 'TotpSecret')
    template = MailTemplate.objects.filter(
        name=TEMPLATE_TOTP_INVITE).first()
    if template is None:
        raise UserError('TOTP invite template is not seeded.')
    with_totp = set(
        TotpSecret.objects.filter(
            user__in=[u.id for u in users], confirmed=True,
        ).values_list('user_id', flat=True)
    )
    invited = []
    for user in users:
        if user.id in with_totp:
            continue
        rendered = template.render(user, extra_context={
            'inviter': inviter, 'invite_url': get_totp_invite_url(),
        })
        dispatch_email(
            rendered['subject'], rendered['body_html'],
            rendered['email_from'] or None, [user.login])
        invited.append(str(user.partner) if user.partner_id else user.login)
    return invited
