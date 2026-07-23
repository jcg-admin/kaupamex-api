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
