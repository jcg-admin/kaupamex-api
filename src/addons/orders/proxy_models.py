"""
Proxy models — addons.orders
Sprint de infraestructura: herencia-modelos-django (T-013)

Tipo de herencia: PROXY (DEC-006).
- Misma tabla: orders_order
- Sin migraciones nuevas
- Open/Closed: añadir un estado nuevo = añadir una clase nueva

Uso:
    from addons.orders.proxy_models import PendingOrder, DeliveredOrder
    PendingOrder.objects.count()        # total de órdenes pendientes de pago
    ActiveOrder.objects.select_related('user')  # órdenes en proceso activo
"""
from django.db import models
from .models import Order



# =============================================================================
# Managers
# =============================================================================

class _StatusManager(models.Manager):
    """Manager base parametrizable por status."""
    _statuses = []

    def get_queryset(self):
        return super().get_queryset().filter(status__in=self._statuses)


class PendingOrderManager(_StatusManager):
    _statuses = [Order.STATUS_PENDING]


class ProcessingOrderManager(_StatusManager):
    _statuses = [Order.STATUS_PROCESSING]


class InPreparationOrderManager(_StatusManager):
    _statuses = [Order.STATUS_IN_PREPARATION]


class ShippedOrderManager(_StatusManager):
    _statuses = [Order.STATUS_SHIPPED]


class DeliveredOrderManager(_StatusManager):
    _statuses = [Order.STATUS_DELIVERED]


class CancelledOrderManager(_StatusManager):
    _statuses = [Order.STATUS_CANCELLED]


class RefundedOrderManager(_StatusManager):
    _statuses = [Order.STATUS_REFUNDED]


class ActiveOrderManager(_StatusManager):
    """Órdenes en cualquier estado 'activo' (no finalizadas)."""
    _statuses = [
        Order.STATUS_PENDING,
        Order.STATUS_PROCESSING,
        Order.STATUS_IN_PREPARATION,
        Order.STATUS_SHIPPED,
    ]


# =============================================================================
# Proxy Models
# =============================================================================

class PendingOrder(Order):
    """Órdenes pendientes de pago. Usan PendingOrderManager."""
    objects = PendingOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden pendiente'


class ProcessingOrder(Order):
    """Órdenes con pago en procesamiento."""
    objects = ProcessingOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden en procesamiento'


class InPreparationOrder(Order):
    """Órdenes en preparación (stock decrementado, en almacén)."""
    objects = InPreparationOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden en preparación'


class ShippedOrder(Order):
    """Órdenes enviadas al transportista."""
    objects = ShippedOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden enviada'


class DeliveredOrder(Order):
    """Órdenes entregadas al comprador."""
    objects = DeliveredOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden entregada'


class CancelledOrder(Order):
    """Órdenes canceladas."""
    objects = CancelledOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden cancelada'


class RefundedOrder(Order):
    """Órdenes reembolsadas."""
    objects = RefundedOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden reembolsada'


class ActiveOrder(Order):
    """
    Vista de órdenes en cualquier estado activo.
    Útil para: proteger ShippingMethod de desactivación,
    calcular carga de trabajo del almacén, etc.
    """
    objects = ActiveOrderManager()
    class Meta:
        proxy        = True
        verbose_name = 'Orden activa'
