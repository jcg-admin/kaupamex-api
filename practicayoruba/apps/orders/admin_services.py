"""
AdminOrderService — apps.orders
Sprint 19 — UC-ORD-07, UC-ORD-08

Lógica de negocio del administrador sobre órdenes.
Reutiliza cancel_order() de services.py con permisos ampliados.
"""
import logging
from django.db import transaction
from django.utils import timezone
from .models import OrderStatusLog, Order
from .services import cancel_order
from django.db.models import Count, Sum, Q
from datetime import timedelta
from apps.payments.models import Payment
from apps.settings_app.models import SiteSettings

logger = logging.getLogger('apps')

# H-ADM-002: Máquina de estados real (FRs usan nombres inexistentes)
# H-ORD-S01: PAGADA añadida — pago confirmado, admin debe poder avanzar o cancelar.
ALLOWED_TRANSITIONS = {
    'PENDING':        ['PROCESSING', 'CANCELLED'],
    'PROCESSING':     ['PAGADA', 'IN_PREPARATION', 'CANCELLED'],
    'PAGADA':         ['IN_PREPARATION', 'CANCELLED'],
    'IN_PREPARATION': ['SHIPPED'],
    'SHIPPED':        ['DELIVERED'],
    # DELIVERED, CANCELLED, REFUNDED → terminales sin transiciones
}

# H-ADM-005: El admin puede cancelar más estados que el comprador
# H-ORD-S01: PAGADA añadida — refund aplica igual que en PROCESSING.
ADMIN_CANCELABLE_STATUSES = ['PENDING', 'PROCESSING', 'PAGADA', 'IN_PREPARATION']


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

        previous = locked.status
        locked.status = new_status
        locked.save(update_fields=['status', 'updated_at'])

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
        locked.order_number, previous, new_status, admin_user.username,
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

        previous = locked.status
        # Reutilizar cancel_order de Sprint 18 (restaura stock + reembolso)
        # pero con los estados admin-cancelables. cancel_order opera sobre
        # la instancia bloqueada dentro del mismo atomic.
        cancel_order(
            order=locked,
            reason=reason,
            cancelled_by=admin_user,
            cancelable_statuses=ADMIN_CANCELABLE_STATUSES,
        )

        # Registrar quién (admin) canceló
        locked.admin_cancelled_by = admin_user
        locked.save(update_fields=['admin_cancelled_by', 'updated_at'])

        OrderStatusLog.objects.create(
            order=locked,
            previous_status=previous,
            new_status='CANCELLED',
            changed_by=admin_user,
            notes=f'[ADMIN] {reason}',
        )

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

    # Bloque 1: Contadores por estado relevantes para el admin
    order_counts = Order.objects.aggregate(
        pending=Count('id', filter=Q(status='PENDING')),
        processing=Count('id', filter=Q(status='PROCESSING')),
        in_preparation=Count('id', filter=Q(status='IN_PREPARATION')),
        shipped=Count('id', filter=Q(status='SHIPPED')),
        total_active=Count('id', filter=~Q(status__in=['DELIVERED', 'CANCELLED', 'REFUNDED'])),
    )

    # Bloque 2: Alertas de expiración — órdenes PENDING > 80% del timeout
    # H-ADM-002: PENDING = PENDING_PAYMENT de la FR
    alert_threshold = now - timedelta(minutes=timeout * 0.8)
    expiring_orders = list(
        Order.objects.filter(
            status='PENDING',
            created_at__lte=alert_threshold,
        )
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

    # Bloque 4: Últimas 10 órdenes
    latest_orders = list(
        Order.objects.select_related('value', 'user')
        .order_by('-created_at')
        .values(
            'order_number', 'status', 'created_at',
            'user__email', 'value__total',
        )[:10]
    )

    return {
        'order_counts':    order_counts,
        'expiring_orders': expiring_orders,
        'day_summary':     day_summary,
        'latest_orders':   latest_orders,
        'payment_timeout_minutes': timeout,
        'generated_at':    now.isoformat(),
    }
