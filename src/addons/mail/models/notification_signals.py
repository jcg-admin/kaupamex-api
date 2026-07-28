"""Signal receivers de notificacion transaccional — familia ``mail``.

Reubicado desde ``notifications.signals`` (slice 3e-2 de la disolucion
notifications->mail). Conecta eventos de dominio (orden, refund, devolucion,
soporte) a los ``notify_*`` de ``mail.notification_service``. En Odoo esto lo
hace ``mail.thread`` (subtypes + automated actions); aqui es la adaptacion de
proyecto por ``@receiver`` sobre los ``post_save``/``pre_save`` de cada dominio.
Wiring: ``MailConfig.ready()`` importa este modulo (los imports de modelos de
orders/payments/returns/support al top son seguros porque el modulo se importa
diferido en ``ready()``). UC-NOT-01..05, UC-NOT-08.

transaction.on_commit en ``notification_service`` garantiza email solo si la
transaccion que disparo el post_save commiteo.

UC-NOT-01: OrderValue.post_save(created=True) — dispara cuando el
  snapshot financiero se persiste, garantizando que instance.total
  esta disponible (Order no tiene campo total directo).

UC-NOT-02: ya NO se dispara por signal (O2C V5d) — la columna espejo
  ``Order.status`` cuyo cambio se observaba fue retirada; cada mutacion de
  eje llama ``notify_order_status_changed`` explicitamente.

UC-NOT-04: ReturnRequest.post_save, transicion a APPROVED/REJECTED.
UC-NOT-05: Refund.post_save(created=True, status=APPROVED).
UC-NOT-08: SupportTicket.post_save(created=False) — transicion a CLOSED.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger('apps')

from addons.orders.models import Order, OrderValue
from addons.payment.models import Refund
from addons.stock.models import ReturnRequest
from addons.helpdesk.models import SupportTicket

from addons.mail.models.notification_service import (
    notify_order_created,
    notify_refund_processed,
    notify_return_processed,
    notify_support_closed,
)


# ── UC-NOT-01: OrderValue created → confirmacion de orden ────────────

@receiver(post_save, sender=OrderValue)
def _order_value_created(sender, instance, created, **kwargs):
    """Dispara UC-NOT-01 cuando el snapshot financiero de la orden se crea."""
    if not created:
        return
    try:
        order = instance.order
        # order.user is None for guest checkouts — notify_order_created handles None
        notify_order_created(order, order.user, instance.total)
    except Exception:
        logger.warning(
            '_order_value_created: notificacion fallida para OrderValue %s',
            instance.pk, exc_info=True,
        )


# ── UC-NOT-02: Order status transition — SIN SIGNAL (O2C V5d) ─────────
#
# El par ``pre_save``/``post_save`` que detectaba la transicion colgaba de la
# escritura de la columna espejo ``orders_order.status``, retirada en V5d: ya no
# existe un campo cuyo cambio observar (el estado se DERIVA de los tres ejes
# canonicos). La notificacion es ahora **explicita** en cada punto de mutacion
# del eje — hub admin, ``cancel_order``, alta de guia, confirmacion de entrega —
# via ``notify_order_status_changed``. Ver H-API-20.


# ── UC-NOT-04: ReturnRequest → APPROVED / REJECTED ─────────────────

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
        order = Order.objects.get(pk=instance.order_id)
    except Order.DoesNotExist:
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


# ── UC-NOT-05: Refund created with APPROVED status ─────────────────

@receiver(post_save, sender=Refund)
def _refund_created(sender, instance, created, **kwargs):
    """Dispara UC-NOT-05 cuando se registra un reembolso aprobado."""
    if not created:
        return
    if instance.status != Refund.STATUS_APPROVED:
        return
    try:
        order = instance.payment.order
        notify_refund_processed(order, order.user, instance.amount)
    except Exception:
        logger.warning(
            '_refund_created: notificacion fallida para Refund %s',
            instance.pk, exc_info=True,
        )


# ── UC-NOT-08: SupportTicket → CLOSED ────────────────────────────

@receiver(pre_save, sender=SupportTicket)
def _cache_ticket_old_status(sender, instance, **kwargs):
    """Captura status anterior para detectar transicion a CLOSED."""
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'status' not in update_fields:
        instance._old_status = getattr(instance, '_old_status', None)
        return
    if instance.pk:
        try:
            instance._old_status = SupportTicket.objects.get(pk=instance.pk).status
        except SupportTicket.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=SupportTicket)
def _support_ticket_closed(sender, instance, created, **kwargs):
    """Dispara UC-NOT-08 cuando el ticket transiciona a CLOSED."""
    if created:
        return
    old = getattr(instance, '_old_status', None)
    if old is None or old == instance.status:
        return
    if instance.status != SupportTicket.Status.CLOSED:
        return
    # closed_by_staff: la vista de cierre manual setea _closed_by_staff;
    # el management command no lo setea, se asume staff (auto-close).
    closed_by_staff = getattr(instance, '_closed_by_staff', True)
    try:
        notify_support_closed(instance, instance.user, closed_by_staff=closed_by_staff)
    except Exception:
        logger.warning(
            '_support_ticket_closed: notificacion fallida para SupportTicket %s',
            instance.pk, exc_info=True,
        )
