"""
signals.py — apps.notifications (UC-NOT-01..05)

Conecta eventos de dominio a notify_* de service.py.
Wiring: NotificationsConfig.ready() importa este modulo.

UC-NOT-01: OrderValue.post_save(created=True) — dispara cuando el
  snapshot financiero se persiste, garantizando que instance.total
  esta disponible (Order no tiene campo total directo).

UC-NOT-02: Order.post_save(created=False) + transicion de status —
  pre_save captura _old_status para detectar cambios sin query extra.

UC-NOT-04: ReturnRequest.post_save, transicion a APPROVED/REJECTED.
UC-NOT-05: Refund.post_save(created=True, status=APPROVED).

transaction.on_commit en service.py garantiza email solo si la
transaccion que disparo el post_save commiteo.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.orders.models import Order, OrderValue
from apps.payments.models import Refund
from apps.returns.models import ReturnRequest

from .service import (
    notify_order_created,
    notify_order_status_changed,
    notify_refund_processed,
    notify_return_processed,
)


# ── UC-NOT-01: OrderValue created → confirmacion de orden ────────────────

@receiver(post_save, sender=OrderValue)
def _order_value_created(sender, instance, created, **kwargs):
    """Dispara UC-NOT-01 cuando el snapshot financiero de la orden se crea."""
    if not created:
        return
    order = instance.order
    notify_order_created(order, order.user, instance.total)


# ── UC-NOT-02: Order status transition ────────────────────────────────

@receiver(pre_save, sender=Order)
def _cache_order_old_status(sender, instance, **kwargs):
    """Captura status anterior para detectar transicion en post_save."""
    if instance.pk:
        try:
            instance._old_status = Order.objects.get(pk=instance.pk).status
        except Order.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Order)
def _order_status_changed(sender, instance, created, **kwargs):
    """Dispara UC-NOT-02 cuando el status de la orden cambia."""
    if created:
        return
    old = getattr(instance, '_old_status', None)
    if old is not None and old != instance.status:
        notify_order_status_changed(instance, instance.status)


# ── UC-NOT-04: ReturnRequest → APPROVED / REJECTED ──────────────────────

@receiver(pre_save, sender=ReturnRequest)
def _cache_return_old_status(sender, instance, **kwargs):
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
        order = Order.objects.get(pk=instance.order_id)
    except Order.DoesNotExist:
        return

    notify_return_processed(
        order,
        instance.user,
        instance.status,
        instance.rejection_reason or None,
    )


# ── UC-NOT-05: Refund created with APPROVED status ──────────────────────

@receiver(post_save, sender=Refund)
def _refund_created(sender, instance, created, **kwargs):
    """Dispara UC-NOT-05 cuando se registra un reembolso aprobado."""
    if not created:
        return
    if instance.status != Refund.STATUS_APPROVED:
        return
    order = instance.payment.order
    notify_refund_processed(order, order.user, instance.amount)
