"""
AdminOrderService — addons.orders
Sprint 19 — UC-ORD-07, UC-ORD-08

Lógica de negocio del administrador sobre órdenes.
Reutiliza cancel_order() de services.py con permisos ampliados.
"""
import logging
from django.db import transaction
from django.utils import timezone
from .models import OrderStatusLog, Order
from .services import cancel_order
from .status_projection import order_status
from django.db.models import Count, Sum, Q, Exists, OuterRef
from datetime import timedelta
from addons.payment.models import Payment
from addons.base.models import SiteSettings
from addons.delivery.models import ShipmentGuide
from addons.sale.models import SaleOrder

logger = logging.getLogger('apps')

# H-ADM-002: Máquina de estados real (FRs usan nombres inexistentes).
# O2C R7 (ADR-024/ADR-026): la máquina habla el VOCABULARIO CANÓNICO de 6
# valores. Se podan los estados MUERTOS PROCESSING/IN_PREPARATION/REFUNDED
# (0 escritores; la proyección canónica nunca los emite — H-API-05/H-API-10),
# colapsando el camino vivo a PENDING → PAID → SHIPPED → DELIVERED (+CANCELLED).
# PAID lo fija el pago aprobado o una conciliación manual del admin; SHIPPED
# exige una guía activa (guard abajo). DRAFT es estado del carrito, no de la
# orden materializada, así que no aparece como origen ni destino.
ALLOWED_TRANSITIONS = {
    'PENDING': ['PAID', 'SHIPPED', 'CANCELLED'],
    'PAID':    ['SHIPPED', 'CANCELLED'],
    'SHIPPED': ['DELIVERED'],
    # DRAFT, DELIVERED, CANCELLED → terminales sin transiciones
}

# H-ADM-005: El admin puede cancelar más estados que el comprador.
# O2C R7: podado al vocabulario canónico — pre-fulfillment (sin guía) es
# cancelable; SHIPPED/DELIVERED no. PROCESSING/IN_PREPARATION eran muertos.
ADMIN_CANCELABLE_STATUSES = ['PENDING', 'PAID']


def transition_order_status(order, new_status: str, admin_user, notes: str = ''):
    """
    Transiciona el estado de una orden validando la máquina de estados.
    UC-ORD-07 (FR-ORD-07.02).

    DEC-AOQ-01: re-lee la orden con ``select_for_update()`` dentro del
    ``transaction.atomic()`` para serializar lecturas concurrentes (la
    instancia ``order`` recibida puede tener status stale). Cierra el
    vector de race condition con 2 admins simultaneos transicionando
    desde el mismo estado inicial.

    Crea OrderStatusLog en cada transición.
    :raises ValueError: si la transición no está permitida.
    """

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        allowed = ALLOWED_TRANSITIONS.get(locked.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Transición no permitida: {locked.status} → {new_status}. "
                f"Transiciones válidas desde {locked.status!r}: "
                f"{allowed or ['ninguna (estado terminal)']}"
            )

        # UC-LOG guard: an order cannot be marked SHIPPED unless it has an
        # active ShipmentGuide.  Without this check an admin can set SHIPPED
        # on an order that has no tracking number, leaving the buyer unable
        # to track the parcel and breaking the logistics audit trail.
        if new_status == 'SHIPPED':
            has_guide = ShipmentGuide.objects.filter(
                order=locked, is_deleted=False,
            ).exists()
            if not has_guide:
                raise ValueError(
                    "La orden no puede marcarse como SHIPPED sin una guía de "
                    "envío activa. Crea la guía en /api/v2/logistics/guides/ "
                    "antes de avanzar este estado."
                )

        previous = locked.status
        locked.status = new_status
        locked.save(update_fields=['status', 'updated_at'])

        # V5b-cancel (H-SALE-10): si el admin cancela, cancelar también la
        # sale.order canónica para que sale.state sea autoritativo.
        if new_status == 'CANCELLED':
            sale = locked.sale_order
            if sale is not None and sale.state != sale.STATE_CANCEL and not sale.locked:
                sale.action_cancel()

        OrderStatusLog.objects.create(
            order=locked,
            previous_status=previous,
            new_status=new_status,
            changed_by=admin_user,
            notes=notes,
        )

        # UC-NOT-02: la notificacion es disparada automaticamente por la
        # signal _order_status_changed (notifications/signals.py) al hacer
        # locked.save() arriba. Llamarla aqui ademas causaba doble envio
        # (una notificacion in-app + email por la signal Y otro por esta
        # linea). Bug detectado en ciclo 43.

    logger.info(
        'Orden %s: %s → %s (admin=%s)',
        locked.order_number, previous, new_status, admin_user.email,
    )
    return locked


def admin_cancel_order(order, reason: str, admin_user):
    """
    Cancela una orden como administrador.
    UC-ORD-08 (FR-ORD-08.01).

    H-ADM-005: el admin puede cancelar IN_PREPARATION (el comprador no).
    El motivo es obligatorio — mínimo 10 caracteres.
    Reutiliza la lógica de cancel_order() con ADMIN_CANCELABLE_STATUSES.

    DEC-AOQ-01: re-lee la orden con ``select_for_update()`` dentro del
    bloque atomic para serializar cancelaciones concurrentes.
    """

    if len(reason.strip()) < 10:
        raise ValueError(
            'El motivo de cancelación es obligatorio y debe tener '
            'al menos 10 caracteres (FR-ORD-08.01).'
        )

    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.status not in ADMIN_CANCELABLE_STATUSES:
            raise ValueError(
                f'El admin no puede cancelar una orden en estado '
                f'{locked.status!r}. Estados cancelables por admin: '
                f'{ADMIN_CANCELABLE_STATUSES}.'
            )

        # Reutilizar cancel_order de Sprint 18 (restaura stock + reembolso)
        # con los estados admin-cancelables. cancel_order ya crea un
        # OrderStatusLog internamente (previous_status + new_status +
        # changed_by + notes). Crear una segunda entrada aquí era duplicado
        # (H-CICLO110-01): cada cancelación admin producía dos filas en
        # el historial — una con notes=reason y otra con notes='[ADMIN] reason'.
        # Se elimina el segundo create; el prefijo [ADMIN] se propaga
        # via admin_reason para que el log único sea identificable.
        admin_reason = f'[ADMIN] {reason}'
        cancel_order(
            order=locked,
            reason=admin_reason,
            cancelled_by=admin_user,
            cancelable_statuses=ADMIN_CANCELABLE_STATUSES,
        )

        # Registrar quién (admin) canceló en el campo dedicado de la orden.
        locked.admin_cancelled_by = admin_user
        locked.save(update_fields=['admin_cancelled_by', 'updated_at'])

    return locked


def get_dashboard_data():
    """
    Calcula los KPIs del dashboard transaccional.
    UC-ORD-10 (4 bloques en una sola respuesta).
    H-ADM-004: usa SiteSettings.payment_timeout_minutes.
    """

    now      = timezone.now()
    settings = SiteSettings.get_current()
    timeout  = settings.payment_timeout_minutes

    # Bloque 1: Contadores por estado relevantes para el admin.
    # O2C V5c-2: los KPIs se derivan de los ejes canónicos (sale.state +
    # Payment + guía), no de la columna espejo ``order.status`` (retirada en
    # V5d). Los estados proyectables se expresan como filtros de queryset
    # equivalentes a ``status_projection.derive_order_status`` (fulfillment
    # gana; luego pago decide PENDING vs PAID). Se usan las relaciones inversas
    # por la FK ``order`` (no-nula) — robusto al ``sale_order`` nulable de la
    # guía (H-API-12).
    _base = Order.objects.annotate(
        _has_approved=Exists(
            Payment.objects.filter(
                order=OuterRef('pk'), status=Payment.STATUS_APPROVED)),
        _has_active_guide=Exists(
            ShipmentGuide.objects.filter(
                order=OuterRef('pk'), is_deleted=False)),
        _has_delivered_guide=Exists(
            ShipmentGuide.objects.filter(
                order=OuterRef('pk'), is_deleted=False,
                status=ShipmentGuide.STATUS_DELIVERED)),
    )
    _is_sale     = Q(sale_order__state=SaleOrder.STATE_SALE)
    _pending_q   = _is_sale & Q(_has_approved=False) & Q(_has_active_guide=False)
    _shipped_q   = _is_sale & Q(_has_active_guide=True) & Q(_has_delivered_guide=False)
    _delivered_q = _is_sale & Q(_has_delivered_guide=True)
    _cancelled_q = Q(sale_order__state=SaleOrder.STATE_CANCEL)

    order_counts = _base.aggregate(
        pending=Count('id', filter=_pending_q),
        shipped=Count('id', filter=_shipped_q),
        # total_active: ni entregada ni cancelada (REFUNDED es valor muerto —
        # 0 escritores, la proyección nunca lo emite — así que excluirlo era
        # no-op).
        total_active=Count('id', filter=~(_delivered_q | _cancelled_q)),
    )
    # PROCESSING e IN_PREPARATION son valores MUERTOS (0 escritores; la
    # proyección canónica nunca los emite — H-API-05/H-API-10). En producción
    # estos contadores ya eran 0; se exponen explícitamente como 0 para
    # preservar la forma del contrato del dashboard. Activar IN_PREPARATION
    # como "pagado, sin guía" es una DECISIÓN DE PRODUCTO separada (ver
    # ``status_projection`` docstring) — no se toma aquí.
    order_counts['processing'] = 0
    order_counts['in_preparation'] = 0

    # Bloque 2: Alertas de expiración — órdenes PENDING > 80% del timeout.
    # PENDING canónico = venta confirmada sin pago aprobado ni guía activa.
    alert_threshold = now - timedelta(minutes=timeout * 0.8)
    expiring_orders = list(
        _base.filter(_pending_q, created_at__lte=alert_threshold)
        .select_related('user')
        .order_by('created_at')
        .values('order_number', 'created_at', 'user__email')[:10]
    )

    # Bloque 3: Resumen del día
    today_start   = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_summary   = Payment.objects.filter(
        status='APPROVED',
        created_at__gte=today_start,
    ).aggregate(
        orders_count=Count('id'),
        total_revenue=Sum('amount'),
    )

    # Bloque 4: Últimas 10 órdenes. El campo ``status`` se deriva de la
    # proyección canónica por fila (no la columna espejo); ``select_related``
    # de ``sale_order`` evita N+1 en ``order_status``.
    latest_orders = [
        {
            'order_number': o.order_number,
            'status':       order_status(o),
            'created_at':   o.created_at,
            'user__email':  o.user.email if o.user_id else None,
            'value__total': getattr(getattr(o, 'value', None), 'total', None),
        }
        for o in (
            Order.objects
            .select_related('value', 'user', 'sale_order')
            .order_by('-created_at')[:10]
        )
    ]

    return {
        'order_counts':    order_counts,
        'expiring_orders': expiring_orders,
        'day_summary':     day_summary,
        'latest_orders':   latest_orders,
        'payment_timeout_minutes': timeout,
        'generated_at':    now.isoformat(),
    }
