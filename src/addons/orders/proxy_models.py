"""Proxy models — addons.orders

Tipo de herencia: PROXY (DEC-006) — misma tabla ``orders_order``, sin tabla
propia.

O2C V5c-3 (cut-over ``orders → sale``, rebanada 5): los dos proxies **vivos**
(``DeliveredOrder``, ``ActiveOrder``) dejan de filtrar la columna espejo
``orders_order.status`` (que se retira en V5d) y derivan su pertenencia de los
**ejes canónicos** — comercial (``sale.SaleOrder.state``), pago
(``payment.Payment``) y fulfillment (guía ``delivery.ShipmentGuide``) — con la
misma semántica que ``status_projection.order_status`` (fulfillment gana; luego
pago decide PENDING vs PAID). Se conserva el guard null-safe de la proyección:
las filas legacy sin enlace canónico (``sale_order_id IS NULL``, pre-V3a) caen a
la columna espejo hasta la data migration de V5d.

Los seis proxies **muertos** (``PendingOrder``, ``ProcessingOrder``,
``InPreparationOrder``, ``ShippedOrder``, ``CancelledOrder``, ``RefundedOrder``)
se eliminan: 0 consumidores en producción (H-API-06, PROVEN). ``PROCESSING``,
``IN_PREPARATION`` y ``REFUNDED`` además son valores muertos del enum (0
escritores; la proyección nunca los emite).

Uso:
    from addons.orders.proxy_models import DeliveredOrder, ActiveOrder
    DeliveredOrder.objects.filter(user=u).exists()   # comprador recurrente
    ActiveOrder.objects.filter(shipping_method=m).count()  # proteger método
"""
from django.db import models
from django.db.models import Q, Exists, OuterRef

from addons.delivery.models import ShipmentGuide
from addons.payment.models import Payment
from addons.sale.models import SaleOrder

from .models import Order


# =============================================================================
# Managers — pertenencia derivada de los ejes canónicos (no la columna espejo)
# =============================================================================

def _with_axis_annotations(queryset):
    """Anota los tres ejes canónicos por fila (mismos ``Exists`` que el
    dashboard O2C en ``admin_services.get_dashboard_data``)."""
    return queryset.annotate(
        _has_approved=Exists(
            Payment.objects.filter(
                order=OuterRef('pk'), status=Payment.STATUS_APPROVED)),
        _has_active_guide=Exists(
            ShipmentGuide.objects.filter(
                order=OuterRef('pk'), is_deleted=False)),
        _has_delivered_guide=Exists(
            ShipmentGuide.objects.filter(
                order=OuterRef('pk'), is_deleted=False,
                status=ShipmentGuide.STATUS_DELIVERED)),
    )


# Fila legacy sin canónica: la proyección ``order_status`` cae a la columna
# espejo (guard null-safe). Se replica aquí para pertenencia idéntica.
_LEGACY = Q(sale_order__isnull=True)
_IS_SALE = Q(sale_order__state=SaleOrder.STATE_SALE)


class DeliveredOrderManager(models.Manager):
    """Órdenes entregadas: guía viva entregada (canónico) o, en filas legacy
    sin canónica, ``status == DELIVERED`` (espejo)."""

    def get_queryset(self):
        base = _with_axis_annotations(super().get_queryset())
        canonical = _IS_SALE & Q(_has_delivered_guide=True)
        legacy = _LEGACY & Q(status=Order.STATUS_DELIVERED)
        return base.filter(canonical | legacy)


class ActiveOrderManager(models.Manager):
    """Órdenes en proceso activo: **toda venta confirmada aún no entregada ni
    cancelada** — ``PENDING ∪ PAID ∪ SHIPPED``.

    H-API-14: se incorpora ``PAID`` (venta pagada sin guía). Antes quedaba
    fuera —herencia del conjunto legacy que sólo cubría
    ``{PENDING, PROCESSING, IN_PREPARATION, SHIPPED}``—, dejando una orden
    pagada-sin-enviar **sin proteger** su ``ShippingMethod`` de la
    desactivación (``settings_app`` UC-CFG-02). Canónicamente el conjunto
    colapsa a *venta confirmada sin guía entregada*; ``PROCESSING`` e
    ``IN_PREPARATION`` siguen siendo valores muertos.
    """

    def get_queryset(self):
        base = _with_axis_annotations(super().get_queryset())
        canonical = _IS_SALE & Q(_has_delivered_guide=False)
        legacy = _LEGACY & Q(status__in=[
            Order.STATUS_PENDING, Order.STATUS_PROCESSING,
            Order.STATUS_IN_PREPARATION, Order.STATUS_PAID,
            Order.STATUS_SHIPPED,
        ])
        return base.filter(canonical | legacy)


# =============================================================================
# Proxy Models
# =============================================================================

class DeliveredOrder(Order):
    """Órdenes entregadas al comprador (eje fulfillment: guía entregada)."""
    objects = DeliveredOrderManager()

    class Meta:
        proxy        = True
        verbose_name = 'Orden entregada'


class ActiveOrder(Order):
    """Órdenes en proceso activo (no finalizadas). Útil para proteger un
    ``ShippingMethod`` de desactivación mientras hay órdenes que lo usan."""
    objects = ActiveOrderManager()

    class Meta:
        proxy        = True
        verbose_name = 'Orden activa'
