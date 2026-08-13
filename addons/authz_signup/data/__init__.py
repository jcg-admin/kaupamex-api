"""Datos semilla del addon — equivalente nativo de ``data/*.xml``.

Adaptación de los config-params de ``auth_signup`` de Odoo
(``auth_signup.invitation_scope`` / ``auth_signup.reset_password``). Mismo
patrón que ``authz_password_policy.data``: el spec es la fuente única que
consumen la data-migration (arranque) y ``seed()`` (re-aplicación sobre el
modelo vivo, H-API-22).

Ambas banderas nacen **abiertas** ('1'), preservando el comportamiento previo
(registro y reset públicos), ahora editables en caliente (L2).

El signup-token core (2º pase) añade: la validez del token por tipo
(``auth_signup.{signup,reset_password}.validity.hours`` de la referencia,
res_partner.py:186-188 — 144h/4h), la URL del SPA de set-password, y las dos
plantillas de correo (``set_password_email`` / ``reset_password_email`` de la
referencia).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import SystemParameter
from addons.mail.models.mail_template import MailTemplate

SIGNUP_PARAMETERS = {
    'authz.signup_allow_uninvited': '1',
    'authz.signup_reset_password': '1',
    'authz_signup.signup_validity_hours': '144',
    'authz_signup.reset_validity_hours': '4',
    'authz_signup.set_password_url': '/account/set-password',
    # Forma propia — la verificación de correo no existe en la referencia.
    'authz_signup.verify_validity_hours': '24',
    'authz_signup.verify_email_url': '/account/verify-email',
}

SIGNUP_TEMPLATES = [
    {
        'name': 'authz_signup: set password',
        'model': 'base.ResUsers',
        'subject': 'Activa tu cuenta',
        'body_html': (
            '<p>Hola {{ object.partner }},</p>'
            '<p>Se creó una cuenta para ti. Fija tu contraseña para '
            'activarla:</p>'
            '<p><a href="{{ link }}">Fijar mi contraseña</a></p>'
        ),
        'auto_delete': True,
    },
    {
        'name': 'authz_signup: reset password',
        'model': 'base.ResUsers',
        'subject': 'Restablece tu contraseña',
        'body_html': (
            '<p>Hola {{ object.partner }},</p>'
            '<p>Recibimos una solicitud para restablecer tu contraseña:</p>'
            '<p><a href="{{ link }}">Restablecer mi contraseña</a></p>'
            '<p>Si no fuiste tú, ignora este correo.</p>'
        ),
        'auto_delete': True,
    },
    {
        'name': 'authz_signup: verify email',
        'model': 'base.ResUsers',
        'subject': 'Verifica tu correo',
        'body_html': (
            '<p>Hola {{ object.partner }},</p>'
            '<p>Confirma que este buzón es tuyo para activar tu cuenta:</p>'
            '<p><a href="{{ link }}">Verificar mi correo</a></p>'
            '<p>El enlace vence en 24 horas.</p>'
        ),
        'auto_delete': True,
    },
]


def seed(using=DEFAULT_DB_ALIAS):
    """Crea las claves ausentes. Idempotente: nunca pisa un valor existente."""
    for key, value in SIGNUP_PARAMETERS.items():
        if not SystemParameter.objects.using(using).filter(key=key).exists():
            SystemParameter.objects.using(using).create(key=key, value=value)
    for spec in SIGNUP_TEMPLATES:
        if not MailTemplate.objects.using(using).filter(
                name=spec['name']).exists():
            MailTemplate.objects.using(using).create(**spec)
