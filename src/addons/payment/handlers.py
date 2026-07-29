"""Receptores de notificación que pertenecen a ``payment`` (UC-NOT-05).

Reubicados desde ``mail/models/notification_signals.py`` (T-035): el receptor
del reembolso vive con ``Refund``, no dentro del addon de correo. Ver la nota
de dirección en ``addons/orders/handlers.py``.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from addons.mail.models.notification_service import notify_refund_processed
from addons.payment.models import Refund

logger = logging.getLogger('apps')


@receiver(post_save, sender=Refund)
def _refund_created(sender, instance, created, **kwargs):
    """Dispara UC-NOT-05 cuando se registra un reembolso aprobado."""
    if not created:
        return
    if instance.status != Refund.STATUS_APPROVED:
        return
    try:
        # I2 (H-API-31): la orden del reembolso se toma de la canónica —
        # tras E4-pre ``payment.order`` es nullable y un pago sólo-canónico
        # perdía la notificación en el ``except`` de abajo.
        order = instance.payment.sale_order
        notify_refund_processed(order, order.partner, instance.amount)
    except Exception:
        logger.warning(
            '_refund_created: notificacion fallida para Refund %s',
            instance.pk, exc_info=True,
        )
