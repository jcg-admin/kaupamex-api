"""Contribución del addon ``sale`` al cliente (``res.partner``).

Fiel a ``sale/models/res_partner.py`` de la referencia, que extiende
``res.partner`` con lo que ``sale`` sabe del cliente
(``sale_order_count``/``sale_order_ids``) vía ``_inherit='res.partner'``. La
identidad vive en ``base`` y **no declara dinero**: los agregados monetarios del
cliente los contribuyen ``sale`` (ventas) y ``account``
(``total_invoiced``/``credit``/``debit``, ``account/models/partner.py:539``).

Aquí vive por tanto el **cálculo**; el addon de identidad sólo lo invoca. Sin
esta separación el agregado de dinero quedaría compuesto dentro de ``users``,
que es el equivalente de declarar ``total_invoiced`` en ``base``.

Adaptación a Django: no hay overlay ``_inherit``, así que la contribución es una
función sobre el partner en vez de un campo inyectado — misma clase de
divergencia ya documentada para ``SaleOrderLine.is_delivery`` y ``ShippingMethod``.
"""
from decimal import Decimal

from django.db.models import Sum

from ..aggregates import with_amounts
from .sale_order import SaleOrder


def lifetime_value(partner) -> Decimal:
    """Valor de vida del cliente: suma de sus ventas confirmadas.

    ``state=sale`` deja fuera dos cosas distintas: las ventas **canceladas** y
    los **carritos** (``draft``). El espejo legacy sólo representaba ventas
    confirmadas, así que bastaba con excluir canceladas; sobre el canónico hay
    que excluir ambas — un carrito abandonado no es valor de vida.
    """
    agg = with_amounts(
        SaleOrder.objects.filter(partner=partner, state=SaleOrder.STATE_SALE)
    ).aggregate(total=Sum('amount_total_sql'))
    return agg['total'] or Decimal('0.00')


def sale_order_count(partner) -> int:
    """Número de ventas confirmadas del cliente (paridad ``sale_order_count``)."""
    return SaleOrder.objects.filter(
        partner=partner, state=SaleOrder.STATE_SALE).count()
