"""Signup con token (set-password), reset de contraseña y alta invitada.

Adaptación fiel de Odoo ``auth_signup/models/res_users.py`` (LGPL-3, 298 loc,
leído completo). Funciones sobre el usuario (Django no permite ``_inherit``).

Métodos de la referencia → aquí:

- ``signup`` → ``signup``: el corazón. Con token → resuelve el partner, invalida
  el token (borra el ``SignupRequest``) y, si el usuario existe, le fija la
  contraseña (set-password); si no, crea el usuario invitado. Sin token →
  alta externa (sólo si el signup público está abierto).
- ``_signup_create_user`` → ``_signup_create_user``: valida scope + email
  único + crea.
- ``reset_password`` / ``_action_reset_password`` → ``reset_password`` /
  ``send_reset_password``: genera el token y envía el correo con el enlace.
- ``_create_user_from_template`` → NO se copia un template user (Odoo copia
  ``base.template_portal_user_id``): aquí el alta pasa por
  ``ResUsers.objects.create_user`` con password inutilizable hasta que el
  usuario lo fije con el token.
- ``state`` (new/active) / ``web_create_users`` / ``send_unregistered_user_reminder``
  / la invitación automática en ``create`` → NO portados: son la UI de
  usuarios del backoffice y un cron de recordatorio; el alta automática por
  correo se dispara explícitamente (``send_reset_password``), no en cada
  ``create``.
"""
import logging

from django.apps import apps as django_apps
from django.utils import timezone

from exceptions import AccessDenied, UserError

from addons.authz_signup.models import res_partner as partner_svc
from addons.authz_signup.models.signup_request import SignupRequest
from addons.authz_signup.models.policy import signup_open
from addons.base.models import SystemParameter
from addons.mail.models.email_executor import dispatch_email
from addons.mail.models.mail_template import MailTemplate

_logger = logging.getLogger(__name__)

TEMPLATE_SET_PASSWORD = 'authz_signup: set password'
TEMPLATE_RESET_PASSWORD = 'authz_signup: reset password'
# URL del SPA donde el usuario fija su contraseña con el token (L2).
PARAM_SET_PASSWORD_URL = 'authz_signup.set_password_url'


class SignupError(Exception):
    """≙ ``SignupError`` (res_partner.py:12-13)."""


def signup(values, token=None):
    """≙ ``signup`` (res_users.py:37-85).

    :param values: dict de campos a escribir (incluye ``password``, y
        ``login``/``email`` en el alta externa).
    :param token: token de signup (opcional).
    :return: ``(login, password)``.
    """
    ResUsers = django_apps.get_model('base', 'ResUsers')
    if token:
        partner = partner_svc.get_partner_from_token(token)
        if partner is None:
            raise UserError(
                "Signup token '%s' is not valid or expired" % token)
        # invalidar el token: borrar el SignupRequest (≙ signup_type=False).
        partner_svc.signup_cancel(partner)
        user = partner.users.first()
        if user is not None:
            # el usuario existe: fijar su contraseña (set-password).
            if values.get('password'):
                user.set_password(values['password'])
                user.save(update_fields=['password'])
            return (user.login, values.get('password'))
        # el usuario no existe: alta del invitado.
        login = values.get('login') or partner.email
        user = ResUsers.objects.create_user(
            login=login, password=values.get('password'), partner=partner)
        return (user.login, values.get('password'))

    # sin token: alta externa (b2c) — sólo si el signup público está abierto.
    return _signup_create_user(values)


def _signup_create_user(values):
    """≙ ``_signup_create_user`` (res_users.py:91-102): valida scope público +
    email único, y crea."""
    ResUsers = django_apps.get_model('base', 'ResUsers')
    if 'partner_id' not in values and not signup_open():
        raise SignupError('Signup is not allowed for uninvited users')
    login = values.get('login') or values.get('email')
    if login and ResUsers.objects.filter(login__iexact=login).exists():
        raise UserError(
            'Another user is already registered using this email address.')
    user = ResUsers.objects.create_user(
        login=login, password=values.get('password'),
        name=values.get('name', ''))
    return (user.login, values.get('password'))


def reset_password(login):
    """≙ ``reset_password`` (res_users.py:131-142): localiza al usuario por
    login o email y le manda el enlace de reset."""
    ResUsers = django_apps.get_model('base', 'ResUsers')
    users = list(ResUsers.objects.filter(login__iexact=login))
    if not users:
        raise UserError('No account found for this login')
    if len(users) > 1:
        raise UserError('Multiple accounts found for this login')
    return send_reset_password(users[0], signup_type=SignupRequest.TYPE_RESET)


def send_reset_password(user, signup_type=SignupRequest.TYPE_RESET):
    """≙ ``_action_reset_password`` (res_users.py:156-230): prepara el signup,
    genera el token y envía el correo con el enlace de set-password."""
    if not user.active:
        raise UserError('You cannot perform this action on an archived user.')
    if not user.login:
        raise UserError(
            'Cannot send email: user %s has no email address.' % user)
    partner_svc.signup_prepare(user.partner, signup_type=signup_type)
    token = partner_svc.generate_signup_token(user.partner)
    base = str(SystemParameter.get_param(
        PARAM_SET_PASSWORD_URL, '/account/set-password'))
    link = '%s?token=%s' % (base, token)

    tmpl_name = (TEMPLATE_RESET_PASSWORD
                 if signup_type == SignupRequest.TYPE_RESET
                 else TEMPLATE_SET_PASSWORD)
    template = MailTemplate.objects.filter(name=tmpl_name).first()
    if template is None:
        raise UserError('Signup mail template %r is not seeded.' % tmpl_name)
    rendered = template.render(user, extra_context={'link': link})
    dispatch_email(
        rendered['subject'], rendered['body_html'],
        rendered['email_from'] or None, [user.login])
    _logger.info('%s email sent for user <%s>', signup_type, user.login)
    return token
