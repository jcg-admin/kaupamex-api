"""Notificaciones de seguridad al activar/desactivar 2FA.

≙ el ``write`` hook de ``auth_totp_mail/models/res_users.py:21-37``: cuando
``totp_secret`` se llena → "2FA Activated"; cuando se vacía → "2FA
Deactivated". Aquí el evento equivalente es la transición de
``TotpSecret.confirmed`` (activación) y el borrado de una fila confirmada
(desactivación) — señales Django en lugar de ``_inherit``.

El correo va directo por ``dispatch_email`` (texto fiel al de la
referencia); el template QWeb ``mail.account_security_alert`` con su
``suggest_2fa`` pertenece a la capa de presentación de Odoo y no se porta.
"""
import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from addons.authz_totp.models import TotpSecret
from addons.mail.models.email_executor import dispatch_email

_logger = logging.getLogger(__name__)


def _notify(user, subject, content):
    if not user.login:
        return
    dispatch_email(subject, content, None, [user.login])


@receiver(pre_save, sender=TotpSecret,
          dispatch_uid='authz_totp_mail_activation')
def notify_totp_activated(sender, instance, **kwargs):
    """Transición ``confirmed`` False→True = 2FA activado."""
    if not instance.confirmed:
        return
    was_confirmed = (
        instance.pk is not None
        and sender.objects.filter(pk=instance.pk, confirmed=True).exists()
    )
    if not was_confirmed:
        _notify(
            instance.user,
            'Security Update: 2FA Activated',
            'Two-factor authentication has been activated on your account',
        )


@receiver(post_delete, sender=TotpSecret,
          dispatch_uid='authz_totp_mail_deactivation')
def notify_totp_deactivated(sender, instance, **kwargs):
    """Borrado de un secreto confirmado = 2FA desactivado."""
    if instance.confirmed:
        _notify(
            instance.user,
            'Security Update: 2FA Deactivated',
            'Two-factor authentication has been deactivated on your account',
        )
