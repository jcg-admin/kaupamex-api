"""Extensión ``sale_loyalty_delivery`` — el envío gratis como recompensa.

Adaptación fiel de Odoo ``sale_loyalty_delivery/models/sale_order.py``
(``odoo19c:``, LGPL-3, ``auto_install``, ``odoo-tools@622ddc2a``; presente
también en ``odoo18c:`` — gobierna 19). Es el puente entre ``sale_loyalty``
y ``delivery``: sus dos extremos existen aquí, así que entra (regla del
puente, ``analisis-gap-sale-contra-ambos-arboles``).

Qué hace la fuente y qué aterriza:

- ``_get_reward_values_free_shipping`` (:35-52) — el corazón: la recompensa
  de envío gratis vale ``-min(discount_max_amount or inf, precio de la
  línea de envío)``. **Se porta** como :func:`free_shipping_discount`.
- ``_get_no_effect_on_threshold_lines`` / ``_get_not_rewarded_order_lines``
  — excluyen las líneas de envío de los umbrales y de los puntos. **Ya
  cubierto localmente**: ``SaleOrderCoupon.discount_base`` filtra
  ``is_delivery=False, is_reward=False``
  (``sale_loyalty/models/sale_order_coupon.py:91``).
- ``_get_claimable_rewards`` (una sola recompensa de envío a la vez) — el
  modelo local ya lo garantiza por forma: ``SaleOrderCoupon`` es OneToOne
  con la orden (un cupón por orden), no hay pila de recompensas que acotar.
- ``loyalty_program``/``loyalty_reward`` (templates de programa +
  ``selection_add`` del tipo) — **ya cubierto**: ``Voucher.TYPE_FREE_
  SHIPPING`` existe en la familia local (``loyalty/models/voucher.py:50``);
  los templates de programa son del configurador UI de Odoo, sin consumidor
  aquí.

Behavior-only (precedente ``sale_stock_margin``): opera sobre los modelos
existentes, sin tabla propia.
"""
from decimal import Decimal

from addons.loyalty.models.voucher import Voucher


def free_shipping_discount(order) -> Decimal:
    """Cuánto descuenta el cupón de envío gratis de esta orden.

    Réplica de ``_get_reward_values_free_shipping``: el valor es el precio
    de la PRIMERA línea de envío (``[:1]`` en la fuente), acotado por
    ``max_discount`` del cupón. Sin cupón FREE_SHIPPING o sin línea de
    envío, cero — el mismo ``or 0`` de la fuente.

    La fuente materializa este valor como línea negativa de recompensa; el
    consumidor local (checkout / ``set_reward_line``) decide la
    materialización — esta función es el contrato del monto.
    """
    coupon = getattr(order, 'coupon', None)
    voucher = coupon.voucher if coupon and coupon.voucher_id else None
    if voucher is None or voucher.voucher_type != Voucher.TYPE_FREE_SHIPPING:
        return Decimal('0.00')
    delivery_line = order.order_line.filter(is_delivery=True).first()
    if delivery_line is None:
        return Decimal('0.00')
    price = delivery_line.price_unit or Decimal('0.00')
    cap = voucher.max_discount
    amount = min(cap, price) if cap is not None else price
    return amount.quantize(Decimal('0.01'))


def amount_total_with_free_shipping(order) -> Decimal:
    """Total de la orden con el envío gratis aplicado.

    Composición con ``SaleOrderCoupon.amount_total_after_discount`` (que
    para FREE_SHIPPING descuenta 0 del subtotal): este addon resta la parte
    del envío. Juntas reproducen el efecto de la línea negativa de la
    fuente sin materializarla.
    """
    coupon = getattr(order, 'coupon', None)
    base = (coupon.amount_total_after_discount()
            if coupon is not None else order.amount_total)
    return base - free_shipping_discount(order)
