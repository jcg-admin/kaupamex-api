"""Contribución del addon ``delivery`` a la orden de venta.

Fiel a Odoo ``delivery/models/sale_order.py``: el envío-como-línea **no es
responsabilidad de** ``sale``. ``delivery`` depende de ``sale``
(``delivery/__manifest__.py:14``), nunca al revés, así que la lógica que
materializa el costo de envío vive aquí y no en el servicio de venta.

Odoo consigue esa dirección con herencia de modelo (``_inherit='sale.order'``
inyecta ``set_delivery_line`` en la orden sin que ``sale`` importe
``delivery``). Django no tiene ese overlay, así que la adaptación es:

- **El comportamiento vive aquí** (este módulo), y el llamador es quien conoce
  el envío — el checkout materializa la línea sobre el **draft**, antes de
  confirmar. Es el mismo orden de Odoo: la línea se agrega a la cotización y
  luego la orden se confirma.
- **El campo marcador** ``SaleOrderLine.is_delivery`` sí queda declarado en
  ``sale`` — Django no permite que una app agregue un campo al modelo de otra.
  Es la misma clase de adaptación que ya usa ``ShippingMethod`` (movido
  *state-only* conservando su tabla física). Divergencia documentada, no
  descuido.

Mecanismo portado: **A — borrar y recrear** (Odoo ``set_delivery_line``, que
nunca actualiza la línea in-place). El Mecanismo B de ``stock_delivery``
(reescritura in-place bajo flag de contexto, para reconciliar el costo
estimado contra el peso real del fulfillment) **no se porta**: este proyecto
no modela ese ciclo.
"""
from decimal import Decimal

from addons.sale.models import SaleOrderLine


def set_delivery_line(order, shipping_cost):
    """Materializa el costo de envío de ``order`` como línea marcada.

    Idempotente por construcción: borra la línea de envío previa y crea una
    nueva, así que llamarla dos veces deja una sola.

    Degradación explícita — devuelve ``None`` sin crear línea cuando:

    - la orden no trae ``carrier`` (el comprador ya no elige transportista: el
      envío se deriva por zona desde que ``update_shipping_method`` quedó
      deprecado), o
    - el importe es 0 (envío gratis: no hay concepto que facturar).

    En ambos casos el importe sigue viviendo en el escalar del espejo. La FK a
    producto es **opcional** por diseño, así que un método sin producto cotiza
    pero todavía no factura como concepto.
    """
    order.order_line.filter(is_delivery=True).delete()
    if order.carrier_id is None or shipping_cost == Decimal('0.00'):
        return None
    return SaleOrderLine.objects.create(
        order=order,
        product=order.carrier.ensure_service_product(),
        name=f'Envío — {order.carrier.name}',
        product_uom_qty=1,
        price_unit=shipping_cost,
        is_delivery=True,
    )
