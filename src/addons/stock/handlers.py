"""Receptores de notificación que pertenecen a ``stock`` (UC-NOT-04).

Reubicados desde ``mail/models/notification_signals.py`` (T-035): el receptor
de la devolución vive con ``ReturnRequest``, no dentro del addon de correo.
Ver la nota de dirección en ``addons/orders/handlers.py``.

``ReturnRequest.order_id`` es un entero, no una FK (desacople deliberado de
``addons.orders``), así que la orden se resuelve por consulta explícita.
"""
import logging

from django.db.models.signals import post_save, pre_save
from addons.sale.models import SaleOrder
from django.dispatch import receiver

from addons.mail.models.notification_service import notify_return_processed
from addons.stock.models import ReturnRequest

logger = logging.getLogger('apps')


@receiver(pre_save, sender=ReturnRequest)
def _cache_return_old_status(sender, instance, **kwargs):
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'status' not in update_fields:
        instance._old_status = getattr(instance, '_old_status', None)
        return
    if instance.pk:
        try:
            instance._old_status = ReturnRequest.objects.get(pk=instance.pk).status
        except ReturnRequest.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=ReturnRequest)
def _return_status_changed(sender, instance, created, **kwargs):
    """Dispara UC-NOT-04 cuando la devolucion pasa a APPROVED o REJECTED."""
    if created:
        return
    old = getattr(instance, '_old_status', None)
    if old is None or old == instance.status:
        return
    if instance.status not in {ReturnRequest.Status.APPROVED, ReturnRequest.Status.REJECTED}:
        return

    try:
        order = SaleOrder.objects.get(pk=instance.order_id)
    except SaleOrder.DoesNotExist:
        return

    try:
        notify_return_processed(
            order,
            instance.user,
            instance.status,
            instance.rejection_reason or None,
        )
    except Exception:
        logger.warning(
            '_return_status_changed: notificacion fallida para ReturnRequest %s',
            instance.pk, exc_info=True,
        )
