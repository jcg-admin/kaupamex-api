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
ALLOWED_TRANSITIONS = {
    'PENDING':        ['PROCESSING', 'CANCELLED'],
    'PROCESSING':     ['IN_PREPARATION', 'CANCELLED'],
    'IN_PREPARATION': ['SHIPPED'],
    'SHIPPED':        ['DELIVERED'],
    # DELIVERED, CANCELLED, REFUNDED → terminales sin transiciones
}

# H-ADM-005: El admin puede cancelar más estados que el comprador
ADMIN_CANCELABLE_STATUSES = ['PENDING', 'PROCESSING', 'IN_PREPARATION']


def transition_order_status(order, new_status: str, admin_user, notes: str = ''):
    """
    Transiciona el estado de una orden validando la máquina de estados.
    UC-ORD-07 (FR-ORD-07.02).

    Crea OrderStatusLog en cada transición.
    :raises ValueError: si la transición no está permitida.
    """

    allowed = ALLOWED_TRANSITIONS.get(order.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Transición no permitida: {order.status} → {new_status}. "
            f"Transiciones válidas desde {order.status!r}: {allowed or ['ninguna (estado terminal)']}"
        )

    previous = order.status
    with transaction.atomic():
        order.status = new_status
        order.save(update_fields=['status'])

        OrderStatusLog.objects.create(
            order=order,
            previous_status=previous,
            new_status=new_status,
            changed_by=admin_user,
            notes=notes,
        )

    logger.info(
        'Orden %s: %s → %s (admin=%s)',
        order.order_number, previous, new_status, admin_user.username,
    )
    return order


def admin_cancel_order(order, reason: str, admin_user):
    """
    Cancela una orden como administrador.
    UC-ORD-08 (FR-ORD-08.01).

    H-ADM-005: el admin puede cancelar IN_PREPARATION (el comprador no).
    El motivo es obligatorio — mínimo 10 caracteres.
    Reutiliza la lógica de cancel_order() con ADMIN_CANCELABLE_STATUSES.
    """

    if len(reason.strip()) < 10:
        raise ValueError(
            'El motivo de cancelación es obligatorio y debe tener '
            'al menos 10 caracteres (FR-ORD-08.01).'
        )

    if order.status not in ADMIN_CANCELABLE_STATUSES:
        raise ValueError(
            f'El admin no puede cancelar una orden en estado {order.status!r}. '
            f'Estados cancelables por admin: {ADMIN_CANCELABLE_STATUSES}.'
        )

    previous = order.status
    # Reutilizar cancel_order de Sprint 18 (restaura stock + reembolso)
    # pero con los estados admin-cancelables
    cancel_order(
        order=order,
        reason=reason,
        cancelled_by=admin_user,
        cancelable_statuses=ADMIN_CANCELABLE_STATUSES,
    )

    # Registrar quién (admin) canceló
    with transaction.atomic():
        order.admin_cancelled_by = admin_user
        order.save(update_fields=['admin_cancelled_by'])

        # Registrar en el log de auditoría
        OrderStatusLog.objects.create(
            order=order,
            previous_status=previous,
            new_status='CANCELLED',
            changed_by=admin_user,
            notes=f'[ADMIN] {reason}',
        )

    return order


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
