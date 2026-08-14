"""Datos semilla del addon — equivalente nativo de ``data/*.xml``.

Dos plantillas (≙ ``mail_template_data.xml``: ``mail_template_totp_invite``
con subject "Invitation to activate two-factor authentication…" y
``mail_template_totp_mail_code`` con subject "Your two-factor authentication
code") + dos config-params L2: la política de 2FA (``auth_totp.policy`` de
la referencia, apagada por default — ``get_param`` sin default) y la URL de
la invitación (en la referencia es la acción del backoffice; el puente de
portal la re-enruta por audiencia).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import SystemParameter
from addons.mail.models.mail_template import MailTemplate

TOTP_MAIL_PARAMETERS = {
    'authz_totp.policy': '',
    'authz_totp_mail.invite_url': '/account/security',
}

TOTP_MAIL_TEMPLATES = [
    {
        'name': 'authz_totp_mail: invitación 2FA',
        'model': 'base.ResUsers',
        'subject': 'Invitación para activar la autenticación en dos pasos '
                   'en tu cuenta',
        'body_html': (
            '<p>Hola {{ object.partner }},</p>'
            '<p>{{ inviter.partner }} te invita a activar la autenticación '
            'en dos pasos (2FA) para proteger tu cuenta.</p>'
            '<p><a href="{{ invite_url }}">Activar la autenticación en dos '
            'pasos</a></p>'
        ),
        'auto_delete': True,
    },
    {
        'name': 'authz_totp_mail: código 2FA',
        'model': 'base.ResUsers',
        'subject': 'Tu código de autenticación en dos pasos',
        'body_html': (
            '<p>Hola {{ object.partner }},</p>'
            '<p>Tu código de verificación es:</p>'
            '<p style="font-size:24px"><strong>{{ code }}</strong></p>'
            '<p>Expira en {{ expiration_minutes }} minutos.</p>'
        ),
        'auto_delete': True,
    },
]


def seed(using=DEFAULT_DB_ALIAS):
    """Crea lo ausente. Idempotente y ``noupdate``: nunca pisa lo existente."""
    for key, value in TOTP_MAIL_PARAMETERS.items():
        if not SystemParameter.objects.using(using).filter(key=key).exists():
            SystemParameter.objects.using(using).create(key=key, value=value)
    for spec in TOTP_MAIL_TEMPLATES:
        if not MailTemplate.objects.using(using).filter(
                name=spec['name']).exists():
            MailTemplate.objects.using(using).create(**spec)
