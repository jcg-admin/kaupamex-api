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

# ------------------------------------------------------------------
# Vocabulario del estado proyectado (E2a del retiro de la entidad espejo).
#
# Vivía en ``orders.Order`` como enum de la columna. Tras V5d la columna no
# existe, pero el vocabulario seguía allí: 39 referencias de producción
# importaban el modelo espejo sólo para leer una constante, y este módulo —el
# que *produce* el estado— importaba el espejo para nombrar su propia salida.
# Acoplamiento invertido, y bloqueante de E5 (no se da de baja ``Order``
# mientras sea el hogar del idioma). Los valores NO cambian: son contrato de
# API pública (``?status=``, Rebanada 6).
# ------------------------------------------------------------------
STATUS_DRAFT                = 'DRAFT'
STATUS_PENDING              = 'PENDING'
STATUS_PROCESSING           = 'PROCESSING'
STATUS_IN_PREPARATION       = 'IN_PREPARATION'
STATUS_SHIPPED              = 'SHIPPED'
STATUS_DELIVERED            = 'DELIVERED'
STATUS_CANCELLED            = 'CANCELLED'
STATUS_CANCELLED_BY_TIMEOUT = 'CANCELLED_TIMEOUT'
STATUS_REFUNDED             = 'REFUNDED'
STATUS_PAID                 = 'PAID'

# Etiquetas para presentación. ``PROCESSING``/``IN_PREPARATION``/``REFUNDED``/
# ``CANCELLED_TIMEOUT`` no los emite la proyección (ver
# ``CANONICAL_ORDER_STATUSES``); se conservan como vocabulario histórico
# alcanzable por datos previos. Su retiro es decisión aparte.
STATUSES = [
    (STATUS_DRAFT,                'Carrito / cotización'),
    (STATUS_PENDING,              'Pendiente de pago'),
    (STATUS_PROCESSING,           'Procesando pago'),
    (STATUS_PAID,                 'Pagado'),
    (STATUS_IN_PREPARATION,       'En preparación'),
    (STATUS_SHIPPED,              'Enviado'),
    (STATUS_DELIVERED,            'Entregado'),
    (STATUS_CANCELLED,            'Cancelado'),
    (STATUS_CANCELLED_BY_TIMEOUT, 'Cancelado por timeout'),
    (STATUS_REFUNDED,             'Reembolsado'),
]


def derive_order_status(sale_order):
    """Proyecta ``STATUSES`` desde los ejes canónicos de ``sale_order``.

    :param sale_order: instancia de ``sale.SaleOrder``.
    :returns: uno de los valores de ``STATUSES`` alcanzables.
    """
    if sale_order.state == SaleOrder.STATE_DRAFT:
        return STATUS_DRAFT
    if sale_order.state == SaleOrder.STATE_CANCEL:
        return STATUS_CANCELLED

    # sale.state == 'sale' (confirmado). Eje fulfillment primero (más
    # avanzado gana): una guía viva significa enviado/entregado.
    guide = getattr(sale_order, 'shipment_guide', None)
    if guide is not None and not guide.is_deleted:
        if guide.status == ShipmentGuide.STATUS_DELIVERED:
            return STATUS_DELIVERED
        return STATUS_SHIPPED

    # Sin guía viva → eje de pago decide PENDING vs PAID.
    approved = sale_order.payments.filter(
        status=Payment.STATUS_APPROVED).exists()
    return STATUS_PAID if approved else STATUS_PENDING


def order_status(order):
    """Estado proyectado de una orden — acepta el espejo o la canónica.

    V5d: la columna espejo ``order.status`` fue retirada y ``sale_order`` es
    obligatorio (``null=False`` + ``PROTECT``), así que el fallback null-safe
    de V5c-2 deja de existir — **toda** ``Order`` deriva de sus ejes. Es la
    única fuente de estado a nivel de objeto.

    I3 (retiro del espejo): esta función es el punto por el que pasa todo
    consumidor del estado proyectado. Mientras exigiera un ``orders.Order``,
    ningún consumidor podía migrar su query al canónico por separado — o
    migraban todos a la vez, o ninguno. Aceptando ambos lados (mismo patrón
    strangler que el puente), cada rebanada migra su propia query sin tocar
    la llamada al proyector, y el día que el espejo desaparezca los
    llamadores ya funcionan.

    :param order: ``orders.Order`` (espejo) o ``sale.SaleOrder`` (canónica).
    """
    sale_order = getattr(order, 'sale_order', order)
    return derive_order_status(sale_order)


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
    STATUS_DRAFT,
    STATUS_PENDING,
    STATUS_PAID,
    STATUS_SHIPPED,
    STATUS_DELIVERED,
    STATUS_CANCELLED,
)


def _is_canonical(queryset) -> bool:
    """``True`` si las filas del queryset son ``SaleOrder``, no el espejo.

    E5/R2 (H-API-98): ``Payment`` y ``ShipmentGuide`` tienen **dos** FK — una al
    espejo (``order``) y otra a la canónica (``sale_order``). El trío de
    queryset de este módulo joineaba siempre por la del espejo, así que mudarlo
    a ``sale/`` sin más lo habría dejado devolviendo vacío en cuanto el espejo
    se vaciara: un fallo silencioso, no un ``ImportError``.

    Aceptar ambas formas es el mismo patrón strangler que :func:`order_status`
    ya usa a nivel de objeto: cada consumidor migra su propia query cuando le
    toca su rebanada, sin coordinar a los diez a la vez.
    """
    return queryset.model is SaleOrder


def annotate_status_axes(queryset):
    """Anota los tres ejes canónicos por fila (mismos ``Exists`` que el
    dashboard O2C y los proxies).

    Acepta queryset de ``SaleOrder`` (canónica) o de ``orders.Order`` (espejo);
    elige la FK del join según cuál sea. Ver :func:`_is_canonical`.
    """
    anchor = 'sale_order' if _is_canonical(queryset) else 'order'
    return queryset.annotate(
        _has_approved=Exists(
            Payment.objects.filter(
                **{anchor: OuterRef('pk')}, status=Payment.STATUS_APPROVED)),
        _has_active_guide=Exists(
            ShipmentGuide.objects.filter(
                **{anchor: OuterRef('pk')}, is_deleted=False)),
        _has_delivered_guide=Exists(
            ShipmentGuide.objects.filter(
                **{anchor: OuterRef('pk')}, is_deleted=False,
                status=ShipmentGuide.STATUS_DELIVERED)),
    )


def _canonical_status_q(status, canonical=False):
    """``Q`` que selecciona las órdenes cuyo estado **proyectado** es
    ``status``, sobre un queryset anotado con :func:`annotate_status_axes`.

    V5d: sin columna espejo ni filas sin canónica, cada rama es puramente
    canónica — el guard null-safe de V5c desapareció junto con el fallback de
    :func:`order_status`.

    :param canonical: ``True`` si las filas ya son ``SaleOrder`` — entonces
        ``state`` se lee directo en vez de navegar ``sale_order__state``
        (E5/R2, H-API-98).
    """
    state_field = 'state' if canonical else 'sale_order__state'
    is_sale = Q(**{state_field: SaleOrder.STATE_SALE})

    if status == STATUS_DRAFT:
        return Q(**{state_field: SaleOrder.STATE_DRAFT})
    if status == STATUS_PENDING:
        return is_sale & Q(_has_approved=False) & Q(_has_active_guide=False)
    if status == STATUS_PAID:
        return is_sale & Q(_has_approved=True) & Q(_has_active_guide=False)
    if status == STATUS_SHIPPED:
        return is_sale & Q(_has_active_guide=True) & Q(_has_delivered_guide=False)
    if status == STATUS_DELIVERED:
        return is_sale & Q(_has_delivered_guide=True)
    if status == STATUS_CANCELLED:
        # ``sale.state='cancel'`` colapsa CANCELLED y CANCELLED_TIMEOUT.
        return Q(**{state_field: SaleOrder.STATE_CANCEL})
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
    canonical = _is_canonical(queryset)
    return annotate_status_axes(queryset).filter(
        _canonical_status_q(status, canonical=canonical))
