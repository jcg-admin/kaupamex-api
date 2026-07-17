"""
Signal handlers — addons.notifications. DEC-BC-19.

Conectado en NotificationsConfig.ready().
Stub: infraestructura para handlers downstream futuros
(analytics, CRM push, marketing emails).
"""
import logging
from django.dispatch import receiver
from addons.orders.signals import order_created

logger = logging.getLogger('apps')


@receiver(order_created)
def handle_order_created(sender, order, **kwargs):
    """
    Handler stub para la señal order_created.
    El BusinessEvent ORDER_CREATED se registra en CheckoutView (view-layer).
    Este handler es el punto de extensión para integraciones futuras
    (email transaccional, CRM, analytics) sin tocar la vista.
    """
    logger.info(
        'order_created signal: orden %s despachada a handlers downstream.',
        order.order_number,
    )
