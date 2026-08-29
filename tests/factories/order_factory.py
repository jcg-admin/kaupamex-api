"""Fábrica canónica de órdenes O2C — post-V5d (ADR-024).

Tras el retiro de la columna espejo ``orders_order.status`` una ``SaleOrder`` **no
tiene estado propio**: se deriva de tres ejes (comercial ``sale.SaleOrder.state``
· pago ``payment.Payment`` · fulfillment ``delivery.ShipmentGuide``). Fabricar
una orden "en estado X" deja de ser fijar un enum y pasa a ser **construir los
hechos** que proyectan X:

===========  ========================================================
Proyectado   Ejes que lo producen
===========  ========================================================
DRAFT        ``sale.state='draft'``
PENDING      ``sale.state='sale'`` sin pago aprobado ni guía
PAID         PENDING + ``Payment`` APPROVED
SHIPPED      PAID + ``ShipmentGuide`` viva (no entregada)
DELIVERED    SHIPPED + guía en ``STATUS_DELIVERED``
CANCELLED    ``sale.state='cancel'``
===========  ========================================================

Sin esta fábrica cada test reconstruye la combinación a mano y es fácil setear
un solo lado de la asimetría de FK (``Payment``/``ShipmentGuide`` apuntan tanto
a ``order`` como a ``sale_order``; la proyección lee el lado ``sale`` y el
filtro anota por ``order`` — ver H-API-20). Aquí se setean **ambos** siempre.
"""
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone

from addons.delivery.models import Courier, ShipmentGuide
from addons.payment.models import Payment
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.models.sale_order import _next_sale_name
from addons.sale.status_projection import (
    STATUSES,
    STATUS_CANCELLED,
    STATUS_DELIVERED,
    STATUS_DRAFT,
    STATUS_PAID,
    STATUS_PENDING,
    STATUS_SHIPPED,
)


_SALE_STATE = {
    STATUS_DRAFT:     SaleOrder.STATE_DRAFT,
    STATUS_CANCELLED: SaleOrder.STATE_CANCEL,
}


def make_courier(**kwargs):
    """Courier mínimo para colgar una guía (``name``/``code`` únicos)."""
    suffix = uuid4().hex[:8]
    kwargs.setdefault('name', f'Courier {suffix}')
    kwargs.setdefault('code', suffix[:20])
    return Courier.objects.create(**kwargs)


def make_order(status=STATUS_PENDING, courier=None, amount=None,
               product=None, quantity=1, unit_price=None,
               **order_kwargs):
    """Crea la ``SaleOrder`` cuyos ejes proyectan ``status``.

    :param status: valor de ``STATUSES`` que debe proyectar
        ``order_status(order)``. Los tres valores muertos del enum
        (``PROCESSING``, ``IN_PREPARATION``, ``REFUNDED``) no son alcanzables:
        la proyección nunca los emite.
    :param courier: courier a reusar para la guía (se crea uno si hace falta).
    :param amount: importe del ``Payment`` cuando el estado lo requiere.
    :param product: producto de la línea canónica. Una venta confirmada
        **siempre** tiene al menos una línea (``action_confirm`` rechaza la
        orden sin ellas, ``sale/models/sale_order.py:198-199``), y desde E4 el
        dinero de los reportes se agrega sobre esas líneas. Un test que
        verifique importes debe pasarlo.
    :param quantity: cantidad de esa línea.
    :param unit_price: precio unitario; por defecto el del producto.
    :param order_kwargs: van a ``SaleOrder.objects.create``. Los nombres del
        espejo retirado se traducen: ``user``→``partner``,
        ``order_number``→``name``, ``shipping_method``→``carrier``.
    :returns: la ``SaleOrder`` creada — es la canónica, no hay espejo.
    """
    # Invariante de producción: action_confirm SIEMPRE fija date_order.
    # Un state='sale' sin date_order es
    # un estado que el flujo real nunca produce (E2c lo filtra como "no
    # comprador"); el factory lo respeta para no fabricar estados imposibles.
    # Un BORRADOR sí lleva fecha, y ésa es la corrección: la referencia declara
    # la columna como *«Creation date of draft/sent orders, Confirmation date
    # of confirmed orders»* — una sola columna con dos significados según el
    # estado, no una fecha que aparece al confirmar. El porte de la cabecera
    # la dejó NOT NULL con default ``timezone.now``, así que el ``None`` que
    # este factory pasaba para el borrador reventaba contra la restricción.
    # I2: ``action_confirm`` asigna SIEMPRE ``name`` (referencia de la
    # secuencia ir.sequence 'sale.order'). Una venta ``state='sale'`` sin
    # ``name`` es un estado que el flujo real nunca produce — y desde I1 la
    # identidad pública se lee de ahí, así que el factory debe respetarlo.
    estado = _SALE_STATE.get(status, SaleOrder.STATE_SALE)
    # E5: el espejo ``orders.Order`` ya no existe. Los kwargs que los tests
    # pasaban al espejo se traducen a los campos canónicos equivalentes; el
    # resto va tal cual a ``SaleOrder``.
    partner_kw = order_kwargs.pop('user', None)
    carrier_kw = order_kwargs.pop('shipping_method', None)
    name_kw    = order_kwargs.pop('order_number', None)
    sale = SaleOrder.objects.create(
        state=estado,
        cart_token=uuid4(),
        name=name_kw or (None if status == STATUS_DRAFT else _next_sale_name()),
        date_order=timezone.now(),
        partner=partner_kw,
        carrier=carrier_kw,
        **order_kwargs,
    )
    # La venta ES la orden: no hay segunda entidad que crear ni que enlazar.
    order = sale

    # E4 / H-API-33 — una venta confirmada sin líneas es un estado imposible:
    # ``action_confirm`` lo rechaza. Mientras el dinero vivía en el espejo el
    # hueco era invisible; ahora los reportes agregan sobre ``order_line``, así
    # que fabricar la venta sin línea produce ingresos en cero y haría fallar
    # al reporte por culpa del fixture, no del código.
    if product is not None and status != STATUS_DRAFT:
        # H-API — ``product.lst_price`` no existe en ``product.ProductProduct``
        # (la variante); el precio de catálogo es ``lst_price`` (odoo19c:
        # ``product_product.py:314-321``, ficha + extra de atributos). Drift
        # heredado de ``catalogue.Product.price``, disuelto en ``product``
        # (H-API-212 y hermanas).
        SaleOrderLine.objects.create(
            order=sale, product=product,
            name=product.name,
            product_uom_qty=quantity,
            price_unit=unit_price if unit_price is not None else product.lst_price,
        )

    if status in (STATUS_PAID, STATUS_SHIPPED,
                  STATUS_DELIVERED):
        Payment.objects.create(
            sale_order=sale,
            gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED,
            amount=amount if amount is not None else Decimal('100.00'),
        )

    if status in (STATUS_SHIPPED, STATUS_DELIVERED):
        delivered = status == STATUS_DELIVERED
        ShipmentGuide.objects.create(
            sale_order=sale,
            courier=courier or make_courier(),
            tracking_number=uuid4().hex[:20],
            status=(ShipmentGuide.STATUS_DELIVERED if delivered
                    else ShipmentGuide.STATUS_IN_TRANSIT),
            delivered_at=timezone.now() if delivered else None,
        )

    return order


def mark_paid(order, amount=None):
    """Lleva una orden existente a PAID **por el eje de pago**.

    Post-V5d no existe columna que escribir: el estado se produce creando el
    hecho. Idempotente — si ya hay un pago aprobado no crea otro.
    """
    sale = order
    if sale.payments.filter(status=Payment.STATUS_APPROVED).exists():
        return order
    Payment.objects.create(
        sale_order=sale,
        gateway=Payment.GATEWAY_MANUAL,
        status=Payment.STATUS_APPROVED,
        amount=amount if amount is not None else Decimal('100.00'),
    )
    return order


def mark_delivered(order, courier=None):
    """Lleva una orden existente a DELIVERED **por el eje de fulfillment**.

    Crea el pago aprobado si falta y la guía entregada; si ya hay guía, la
    marca entregada en vez de crear una segunda (la relación es OneToOne).
    """
    mark_paid(order)
    sale = order
    guide = getattr(sale, 'shipment_guide', None)
    if guide is None:
        ShipmentGuide.objects.create(
            sale_order=sale,
            courier=courier or make_courier(),
            tracking_number=uuid4().hex[:20],
            status=ShipmentGuide.STATUS_DELIVERED,
            delivered_at=timezone.now(),
        )
    else:
        guide.status = ShipmentGuide.STATUS_DELIVERED
        guide.delivered_at = timezone.now()
        guide.save(update_fields=['status', 'delivered_at', 'updated_at'])
    return order
