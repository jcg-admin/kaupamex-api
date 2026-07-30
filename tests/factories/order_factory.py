"""Fábrica canónica de órdenes O2C — post-V5d (ADR-024).

Tras el retiro de la columna espejo ``orders_order.status`` una ``Order`` **no
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
from addons.orders.models import Order
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
    """Crea el par ``Order`` + ``SaleOrder`` cuyos ejes proyectan ``status``.

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
    :param order_kwargs: se pasan tal cual a ``Order.objects.create``.
    :returns: la ``Order`` creada (su canónica está en ``order.sale_order``).
    """
    # Invariante de producción: action_confirm SIEMPRE fija date_order, y
    # el espejo sólo existe post-confirm. Un state='sale' sin date_order es
    # un estado que el flujo real nunca produce (E2c lo filtra como "no
    # comprador"); el factory lo respeta para no fabricar estados imposibles.
    # I2: ``action_confirm`` asigna SIEMPRE ``name`` (referencia de la
    # secuencia ir.sequence 'sale.order'). Una venta ``state='sale'`` sin
    # ``name`` es un estado que el flujo real nunca produce — y desde I1 la
    # identidad pública se lee de ahí, así que el factory debe respetarlo.
    estado = _SALE_STATE.get(status, SaleOrder.STATE_SALE)
    sale = SaleOrder.objects.create(
        state=estado,
        cart_token=uuid4(),
        name=(None if status == STATUS_DRAFT else _next_sale_name()),
        date_order=(None if status == STATUS_DRAFT else timezone.now()),
        # Producción setea ambos lados del actor (confirm_draft_order crea el
        # espejo con user=order.partner); el factory replica esa consistencia.
        partner=order_kwargs.get('user'),
    )
    order = Order.objects.create(sale_order=sale, **order_kwargs)

    # E4 / H-API-33 — una venta confirmada sin líneas es un estado imposible:
    # ``action_confirm`` lo rechaza. Mientras el dinero vivía en el espejo el
    # hueco era invisible; ahora los reportes agregan sobre ``order_line``, así
    # que fabricar la venta sin línea produce ingresos en cero y haría fallar
    # al reporte por culpa del fixture, no del código.
    if product is not None and status != STATUS_DRAFT:
        SaleOrderLine.objects.create(
            order=sale, product=product,
            name=product.name,
            product_uom_qty=quantity,
            price_unit=unit_price if unit_price is not None else product.price,
        )

    if status in (STATUS_PAID, STATUS_SHIPPED,
                  STATUS_DELIVERED):
        Payment.objects.create(
            order=order, sale_order=sale,
            gateway=Payment.GATEWAY_MANUAL,
            status=Payment.STATUS_APPROVED,
            amount=amount if amount is not None else Decimal('100.00'),
        )

    if status in (STATUS_SHIPPED, STATUS_DELIVERED):
        delivered = status == STATUS_DELIVERED
        ShipmentGuide.objects.create(
            order=order, sale_order=sale,
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
    sale = order.sale_order
    if sale.payments.filter(status=Payment.STATUS_APPROVED).exists():
        return order
    Payment.objects.create(
        order=order, sale_order=sale,
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
    sale = order.sale_order
    guide = getattr(sale, 'shipment_guide', None)
    if guide is None:
        ShipmentGuide.objects.create(
            order=order, sale_order=sale,
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
