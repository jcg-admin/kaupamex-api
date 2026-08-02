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

from addons.product.models import ProductProduct, ProductTemplate
from addons.product.models.product_template import TYPE_SERVICE
from addons.sale.models import SaleOrderLine


# Producto de servicio **genérico** del envío. La semilla por método
# (``ShippingMethod.ensure_service_product``) cubre el caso en que el comprador
# elige transportista; pero el flujo real de este e-commerce deriva el envío
# **por zona** (``orders/shipping.py::resolve_shipping_quote``) y la orden
# queda sin ``carrier``. Ese envío se cobra igual, así que necesita su concepto
# — mismo criterio que el descuento, que tampoco tiene "método" y usa un
# producto global (``sale_loyalty.ensure_reward_product``). Ver H-API-42.
GENERIC_SERVICE_SKU = 'SRV-ENVIO'


def ensure_generic_service_product():
    """Producto de servicio del envío sin transportista. Idempotente.

    H-API — creaba la **variante** (``product.ProductProduct``, el
    ``related_model`` de ``SaleOrderLine.product``) con kwargs de
    ``catalogue.Product`` (``sku``/``slug``/``price``/``is_active``/
    ``is_published``/``short_description``): ninguno existe en el catálogo
    canónico, que separa ficha (``ProductTemplate.name``/``list_price``/
    ``active``) de variante (``ProductProduct.default_code``/``active``).
    Drift heredado de la disolución de ``catalogue`` en ``product``
    (H-API-212 y hermanas) — nunca se había ejercido con datos reales, sólo
    fallaba silenciosamente en tests que mockeaban el gateway antes de
    llegar aquí.
    """
    variant = (ProductProduct.objects
              .filter(default_code=GENERIC_SERVICE_SKU).first())
    if variant is not None:
        return variant
    tmpl = ProductTemplate.objects.create(
        name='Envío', type=TYPE_SERVICE,
        list_price=Decimal('0.00'), sale_ok=False, active=True,
    )
    return ProductProduct.objects.create(
        product_tmpl=tmpl, default_code=GENERIC_SERVICE_SKU, active=True,
    )


def set_delivery_line(order, shipping_cost):
    """Materializa el costo de envío de ``order`` como línea marcada.

    Idempotente por construcción: borra la línea de envío previa y crea una
    nueva, así que llamarla dos veces deja una sola.

    **El transportista es opcional.** Si la orden trae ``carrier``, la línea
    usa el producto de servicio de ese método y lo nombra; si no —el caso real,
    porque el envío se deriva por zona desde que ``update_shipping_method``
    quedó deprecado— usa el producto genérico. Lo que decide si hay línea es el
    **importe**, no el transportista: un envío cobrado siempre es un concepto
    facturable, y omitirlo dejaba el total del canónico por debajo de lo que el
    comprador paga (H-API-42).

    Devuelve ``None`` sólo cuando el importe es 0 (envío gratis): no hay
    concepto que facturar.

    El borrado de la línea previa es un ``QuerySet.delete()`` en bloque, que
    no dispara el recálculo de ``SaleOrderLine.delete()`` (H-API-30); en la
    rama que crea la línea nueva el recálculo llega igual vía
    ``SaleOrderLine.save()``, pero la rama "envío gratis" no crea nada, así
    que aquí se dispara explícito para no dejar la orden con un total stale.
    """
    order.order_line.filter(is_delivery=True).delete()
    if shipping_cost == Decimal('0.00'):
        order._compute_amounts()
        return None
    carrier = order.carrier if order.carrier_id else None
    return SaleOrderLine.objects.create(
        order=order,
        product=(carrier.ensure_service_product() if carrier
                 else ensure_generic_service_product()),
        name=(f'Envío — {carrier.name}' if carrier else 'Envío'),
        product_uom_qty=1,
        price_unit=shipping_cost,
        is_delivery=True,
    )


def amount_delivery(order):
    """Importe de envío de la orden — suma de sus líneas ``is_delivery``.

    Contraparte por-orden de ``delivery/aggregates.py`` (que agrega sobre
    muchas). Fiel a ``website_sale._compute_amount_delivery``
    (``website_sale/models/sale_order.py:62-69``), que resuelve el mismo dato
    filtrando ``order_line.filtered('is_delivery')`` — vive en el módulo que
    conoce el envío, no en ``sale``.
    """
    return sum((line.price_total()
                for line in order.order_line.filter(is_delivery=True)),
               Decimal('0.00'))
