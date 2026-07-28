"""Contribución del addon ``sale_loyalty`` a la orden de venta.

Simétrico de ``delivery/models/sale_order.py`` y por la misma razón: en Odoo
la recompensa es una **línea de precio negativo** que ``sale_loyalty``
contribuye a ``sale.order``, no algo que ``sale`` sepa calcular. La dirección
de dependencia es ``sale_loyalty`` → ``sale``, nunca al revés.

Envío y descuento comparten mecanismo por decisión del ejecutor
(2026-07-28, monolito modular): misma forma de línea marcada, mismo ciclo de
borrar-y-recrear, mismos dos hogares separados — cada addon contribuye lo
suyo.
"""
from decimal import Decimal

from addons.sale.models import SaleOrderLine

from .sale_order_coupon import SaleOrderCoupon, ensure_reward_product


def set_reward_line(order):
    """Materializa el descuento del cupón como línea de precio negativo.

    El importe **no se recibe**: se calcula del cupón aplicado a la orden
    (``SaleOrderCoupon.discount_amount()``), que es quien lo sabe. Así el
    llamador no tiene que replicar la regla de descuento y no puede
    desincronizarse de ella.

    Idempotente: borra la línea de recompensa previa y crea una nueva.
    Devuelve ``None`` si la orden no trae cupón o el descuento es 0.
    """
    order.order_line.filter(is_reward=True).delete()
    coupon = SaleOrderCoupon.objects.filter(order=order).first()
    if coupon is None:
        return None
    discount = coupon.discount_amount()
    if discount == Decimal('0.00'):
        return None
    return SaleOrderLine.objects.create(
        order=order,
        product=ensure_reward_product(),
        name='Descuento',
        product_uom_qty=1,
        price_unit=-discount,
        is_reward=True,
    )
