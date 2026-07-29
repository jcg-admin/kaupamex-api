"""Receptores de notificación que pertenecen a ``orders`` (UC-NOT-01).

Reubicados desde ``mail/models/notification_signals.py`` (T-035). La dirección
anterior era ``mail`` → ``orders``: el addon de correo importaba el modelo de
negocio para colgarle un ``post_save``. En la referencia ``mail`` está en
profundidad 4 y los addons de negocio entre 7 y 10, y la dependencia apunta
siempre hacia abajo: es el addon de negocio quien conoce a ``mail``, nunca al
revés. Aquí el receptor vive con su modelo y llama al servicio de ``mail``.

``transaction.on_commit`` dentro de ``notification_service`` garantiza que el
correo sólo sale si la transacción que disparó el ``post_save`` commiteó.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from addons.mail.models.notification_service import notify_order_created
from addons.orders.models import OrderValue
from addons.orders.signals import order_created

logger = logging.getLogger('apps')


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


# ── Punto de extensión downstream (DEC-BC-19) ────────────────────────
#
# Reubicado desde ``mail/models/notification_handlers.py`` (T-035). Era la
# última arista ``mail`` → ``orders``: el addon de correo importaba la señal
# de ``orders`` para recibirla. El receptor no hace nada propio de correo
# —sólo registra—, así que su hogar es el addon dueño de la señal.


@receiver(order_created)
def handle_order_created(sender, order, **kwargs):
    """Handler stub para la señal ``order_created``.

    El BusinessEvent ORDER_CREATED se registra en CheckoutView (view-layer).
    Este handler es el punto de extensión para integraciones futuras
    (email transaccional, CRM, analytics) sin tocar la vista.
    """
    logger.info(
        'order_created signal: orden %s despachada a handlers downstream.',
        order.order_number,
    )
