"""Señales del núcleo ``sale`` — punto de extensión para los satélites.

En Odoo un satélite extiende al núcleo con ``_inherit``: ``sale_loyalty``
añade el cupón a ``sale.order`` sin que ``sale`` sepa que ``sale_loyalty``
existe. Django no tiene ``_inherit``; su punto de extensión nativo son las
señales.

Este módulo las declara para invertir la dirección de dependencia (T-034):
el núcleo **emite**, el satélite **escucha**. ``sale`` no importa a ningún
``sale_*``.
"""
import django.dispatch

# Emitida por ``get_draft_totals`` para recolectar descuentos aplicables al
# draft. Cada receptor devuelve un ``Decimal`` (0 si no aplica); el núcleo
# suma las respuestas. ``sale_loyalty`` responde con el descuento del cupón.
#
#   :param sender: la clase ``SaleOrder``
#   :param order: la orden en draft
#   :param subtotal: base sobre la que calcular el descuento
#   :return (por receptor): Decimal
draft_discount_requested = django.dispatch.Signal()


# Emitida donde el núcleo necesita el objeto voucher del draft (no sólo su
# importe): el consumo al confirmar. ``sale_loyalty`` responde con el
# ``Voucher`` del cupón, o ``None``.
#
#   :param sender: la clase ``SaleOrder``
#   :param order: la orden
#   :return (por receptor): Voucher | None
draft_voucher_requested = django.dispatch.Signal()

# Emitida al final de ``confirm_draft_order``, dentro de la transacción.
# Cada satélite hace lo suyo: ``sale_stock`` abre el seguimiento de entrega,
# ``sale_loyalty`` consume el voucher.
#
#   :param sender: la clase ``SaleOrder``
#   :param order: la orden ya confirmada
#   :param subtotal: base de la venta (para calcular el consumo)
order_confirmed = django.dispatch.Signal()
