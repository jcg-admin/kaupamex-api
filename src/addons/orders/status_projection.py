"""Proyección del estado legacy ``Order.status`` desde los ejes canónicos.

V5c de la unificación orders→sale (``analisis-unificar-orders-sale``,
H-SALE-09). El enum monolítico ``Order.status`` colapsa tres ejes que en
Odoo viven en modelos separados: comercial (``sale.order.state``), pago
(``payment.transaction`` ≈ ``Payment``) y fulfillment (``stock.picking`` /
guía ≈ ``ShipmentGuide``). Esta función **proyecta** el enum legacy desde
esos ejes, de modo que los lectores puedan derivar el estado sin depender
de la columna ``orders_order.status`` (que se retira en V5d).

Reproduce el estado **observable** del espejo ``orders.Order`` para los
estados que el flujo vivo realmente produce. Los valores legacy que
**ningún escritor fija** — ``PROCESSING``, ``IN_PREPARATION``,
``REFUNDED`` (PROVEN: 0 escrituras fuera de migraciones/enum) — no se
emiten: la proyección es fiel a la realidad, no al enum. La activación de
``IN_PREPARATION`` (ya poblado en el eje canónico por V5b) es una decisión
de producto separada; hasta entonces el mismo estado observable (``PAID``)
se preserva.

Limitación conocida (gap documentado en H-SALE-09): ``sale.state='cancel'``
colapsa ``CANCELLED`` y ``CANCELLED_TIMEOUT`` — la razón de cancelación
(timeout) es un sub-eje aún no anclado; la proyección devuelve
``CANCELLED`` para ambos.
"""
from django.db.models import Q, Exists, OuterRef

from addons.delivery.models import ShipmentGuide
from addons.payment.models import Payment
from addons.sale.models import SaleOrder

from .models import Order


def derive_order_status(sale_order):
    """Proyecta ``Order.STATUSES`` desde los ejes canónicos de ``sale_order``.

    :param sale_order: instancia de ``sale.SaleOrder``.
    :returns: uno de los valores de ``Order.STATUSES`` alcanzables.
    """
    if sale_order.state == SaleOrder.STATE_DRAFT:
        return Order.STATUS_DRAFT
    if sale_order.state == SaleOrder.STATE_CANCEL:
        return Order.STATUS_CANCELLED

    # sale.state == 'sale' (confirmado). Eje fulfillment primero (más
    # avanzado gana): una guía viva significa enviado/entregado.
    guide = getattr(sale_order, 'shipment_guide', None)
    if guide is not None and not guide.is_deleted:
        if guide.status == ShipmentGuide.STATUS_DELIVERED:
            return Order.STATUS_DELIVERED
        return Order.STATUS_SHIPPED

    # Sin guía viva → eje de pago decide PENDING vs PAID.
    approved = sale_order.payments.filter(
        status=Payment.STATUS_APPROVED).exists()
    return Order.STATUS_PAID if approved else Order.STATUS_PENDING


def order_status(order):
    """Estado legacy de un ``orders.Order`` derivado de su canónica.

    Transición V5c-2: los lectores object-level dejan de leer la columna
    ``order.status`` y derivan de los ejes canónicos vía la O2O
    ``Order.sale_order`` (fijada por el confirm, V3a). Guarda null-safe:
    filas legacy sin enlace canónico (pre-V3a) caen a la columna hasta la
    data migration (V5d). Comportamiento equivalente probado en
    ``test_status_projection`` (``derive == legacy.status``).
    """
    if order.sale_order_id is None:
        return order.status
    return derive_order_status(order.sale_order)


# ---------------------------------------------------------------------------
# Filtro canónico del contrato público ``?status=`` (O2C rebanada 6)
# ---------------------------------------------------------------------------

# Vocabulario público del ``?status=`` de ``orders/``: los estados que la
# proyección canónica realmente alcanza para una ``Order`` materializada.
# ``DRAFT`` se acepta por completitud del contrato pero no lo alcanza ninguna
# ``Order`` (el espejo se materializa en el confirm, V3a, ya con
# ``sale.state='sale'``). Los tres valores muertos del enum legacy
# (``PROCESSING``, ``IN_PREPARATION``, ``REFUNDED``) quedan **fuera** del
# contrato: la proyección nunca los emite.
CANONICAL_ORDER_STATUSES = (
    Order.STATUS_DRAFT,
    Order.STATUS_PENDING,
    Order.STATUS_PAID,
    Order.STATUS_SHIPPED,
    Order.STATUS_DELIVERED,
    Order.STATUS_CANCELLED,
)


def annotate_status_axes(queryset):
    """Anota los tres ejes canónicos por fila (mismos ``Exists`` que el
    dashboard O2C y los proxies)."""
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


def _canonical_status_q(status):
    """``Q`` que selecciona las órdenes cuyo estado **proyectado** es
    ``status``, sobre un queryset anotado con :func:`annotate_status_axes`.

    Guard null-safe: las filas legacy sin canónica (``sale_order_id IS NULL``,
    pre-V3a) caen a la columna espejo, idéntico a :func:`order_status`.
    """
    legacy = Q(sale_order__isnull=True)
    is_sale = Q(sale_order__state=SaleOrder.STATE_SALE)

    if status == Order.STATUS_DRAFT:
        return (Q(sale_order__state=SaleOrder.STATE_DRAFT)
                | (legacy & Q(status=Order.STATUS_DRAFT)))
    if status == Order.STATUS_PENDING:
        return ((is_sale & Q(_has_approved=False) & Q(_has_active_guide=False))
                | (legacy & Q(status=Order.STATUS_PENDING)))
    if status == Order.STATUS_PAID:
        return ((is_sale & Q(_has_approved=True) & Q(_has_active_guide=False))
                | (legacy & Q(status=Order.STATUS_PAID)))
    if status == Order.STATUS_SHIPPED:
        return ((is_sale & Q(_has_active_guide=True) & Q(_has_delivered_guide=False))
                | (legacy & Q(status=Order.STATUS_SHIPPED)))
    if status == Order.STATUS_DELIVERED:
        return ((is_sale & Q(_has_delivered_guide=True))
                | (legacy & Q(status=Order.STATUS_DELIVERED)))
    if status == Order.STATUS_CANCELLED:
        # ``sale.state='cancel'`` colapsa CANCELLED y CANCELLED_TIMEOUT.
        return (Q(sale_order__state=SaleOrder.STATE_CANCEL)
                | (legacy & Q(status__in=[Order.STATUS_CANCELLED,
                                          Order.STATUS_CANCELLED_BY_TIMEOUT])))
    raise ValueError(status)


def filter_orders_by_status(queryset, status):
    """Filtra ``queryset`` de ``Order`` por su estado **proyectado** ``status``
    (contrato público ``?status=``), derivándolo de los ejes canónicos en vez
    de la columna espejo ``orders_order.status`` (que se retira en V5d).

    :raises ValueError: si ``status`` no está en :data:`CANONICAL_ORDER_STATUSES`
        (el llamador lo traduce a un 400 ``INVALID_STATUS``).
    """
    if status not in CANONICAL_ORDER_STATUSES:
        raise ValueError(status)
    return annotate_status_axes(queryset).filter(_canonical_status_q(status))
