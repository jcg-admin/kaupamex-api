"""
Aggregations — apps.reports

Pure-Python helpers that build the report payloads for UC-REP-01..04.
Each function returns a dict ready to be serialized by the view layer.
Identifiers + JSON keys in English (DEC-DOC-005).
"""
from datetime import timedelta
from decimal import Decimal
from django.db.models import Count, F, Sum, Max as models_Max
from django.db.models.functions import TruncDate
from django.utils import timezone
from apps.orders.models import Order, OrderValue, OrderItem
from apps.payments.models import Payment
from apps.catalogue.models import Product
from apps.inventory.models import StockAlert
from apps.support.models import SupportTicket



# ────────────────────────── Period parsing ─────────────────────────────────

DEFAULT_PERIOD_DAYS = 30
MAX_PERIOD_DAYS = 366  # ~1 year — prevents multi-year DoS queries


def parse_period(value: str | None) -> int:
    """
    Parse a period string like '7d', '30d', '90d', '12m'.
    Returns the number of days. Falls back to DEFAULT_PERIOD_DAYS.
    Capped at MAX_PERIOD_DAYS to prevent DoS via huge date ranges.
    """
    if not value:
        return DEFAULT_PERIOD_DAYS
    value = value.strip().lower()
    try:
        if value.endswith('d'):
            days = max(1, int(value[:-1]))
        elif value.endswith('m'):
            days = max(1, int(value[:-1]) * 30)
        else:
            days = max(1, int(value))
    except (ValueError, TypeError):
        return DEFAULT_PERIOD_DAYS
    return min(days, MAX_PERIOD_DAYS)


def period_window(days: int):
    end = timezone.now()
    start = end - timedelta(days=days)
    return start, end


# ────────────────────────── UC-REP-01 sales ────────────────────────────────

def build_sales_payload(period_days: int) -> dict:

    start, end = period_window(period_days)
    prev_start = start - timedelta(days=period_days)
    prev_end = start

    qs = Order.objects.filter(
        created_at__gte=start, created_at__lte=end,
    ).exclude(status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])  # D-03

    totals_agg = OrderValue.objects.filter(order__in=qs).aggregate(
        revenue=Sum('total'),
        order_count=Count('id'),
    )
    revenue = totals_agg['revenue'] or Decimal('0.00')
    order_count = totals_agg['order_count'] or 0

    prev_qs = Order.objects.filter(
        created_at__gte=prev_start, created_at__lt=prev_end,
    ).exclude(status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])
    prev_agg = OrderValue.objects.filter(order__in=prev_qs).aggregate(
        revenue=Sum('total'),
        order_count=Count('id'),
    )
    prev_revenue = prev_agg['revenue'] or Decimal('0.00')
    prev_count = prev_agg['order_count'] or 0

    def pct_delta(curr, prev):
        if prev == 0:
            return None
        return float((Decimal(curr) - Decimal(prev)) / Decimal(prev) * 100)

    series_rows = (
        OrderValue.objects.filter(order__in=qs)
        .annotate(day=TruncDate('order__created_at'))
        .values('day')
        .annotate(revenue=Sum('total'), orders=Count('id'))
        .order_by('day')
    )
    series = [
        {
            'date': r['day'].isoformat() if r['day'] else None,
            'revenue': str(r['revenue'] or Decimal('0.00')),
            'orders': r['orders'],
        }
        for r in series_rows
    ]

    payment_rows = (
        Payment.objects.filter(
            created_at__gte=start, created_at__lte=end,
            status=Payment.STATUS_APPROVED,
        )
        .values('gateway')
        .annotate(amount=Sum('amount'), count=Count('id'))
        .order_by('-amount')
    )
    payment_breakdown = [
        {
            'gateway': r['gateway'],
            'amount': str(r['amount'] or Decimal('0.00')),
            'count': r['count'],
        }
        for r in payment_rows
    ]

    return {
        'totals': {
            'revenue': str(revenue),
            'orders': order_count,
            'average_ticket': str(
                (revenue / order_count).quantize(Decimal('0.01'))
                if order_count else Decimal('0.00')
            ),
        },
        'comparison': {
            'previous_revenue': str(prev_revenue),
            'previous_orders': prev_count,
            'revenue_delta_pct': pct_delta(revenue, prev_revenue),
            'orders_delta_pct': pct_delta(order_count, prev_count),
        },
        'series': series,
        'payment_breakdown': payment_breakdown,
    }


# ────────────────────────── UC-REP-02 top sellers ──────────────────────────

def build_top_sellers_payload(
    period_days: int, limit: int = 10, sort_by: str = 'UNIDADES',
) -> dict:
    # D-09: sort_by 'UNIDADES' (default) or 'INGRESOS'.
    start, end = period_window(period_days)
    order_field = '-revenue' if sort_by == 'INGRESOS' else '-units_sold'

    rows = (
        OrderItem.objects
        .filter(order__created_at__gte=start, order__created_at__lte=end)
        .exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])  # H-CICLO27-03: alinear con build_sales_payload
        .values('product_id', 'product_name', 'sku')
        .annotate(units_sold=Sum('quantity'), revenue=Sum('subtotal'))
        .order_by(order_field)[:limit]
    )
    raw_results = [
        {
            'product_id': r['product_id'],
            'product_name': r['product_name'],
            'sku': r['sku'],
            'units_sold': r['units_sold'] or 0,
            'revenue': r['revenue'] or Decimal('0.00'),
        }
        for r in rows
    ]
    total_revenue = sum(r['revenue'] for r in raw_results) or Decimal('0.00')
    results = [
        {
            **r,
            'revenue': str(r['revenue']),
            'share_pct': round(float(r['revenue'] / total_revenue * 100), 2)
            if total_revenue else None,
        }
        for r in raw_results
    ]

    total_inactive = Product.objects.filter(is_active=False).count()
    inactive_with_sales = (
        OrderItem.objects
        .filter(order__created_at__gte=start, order__created_at__lte=end)
        .exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])
        .filter(product__is_active=False)
        .values('product_id').distinct().count()
    )
    inactive_no_sales = max(0, total_inactive - inactive_with_sales)
    inactive_no_sales_pct = (
        float(inactive_no_sales) / total_inactive * 100
        if total_inactive else 0.0
    )
    return {
        'results': results,
        'inactive_no_sales_pct': round(inactive_no_sales_pct, 2),
    }


# ────────────────────────── UC-REP-03 dashboard ────────────────────────────

def build_dashboard_payload() -> dict:

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_qs = Order.objects.filter(
        created_at__gte=today_start,
    ).exclude(status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])  # H-CICLO28-01
    today_agg = OrderValue.objects.filter(order__in=today_qs).aggregate(
        revenue=Sum('total'), order_count=Count('id'),
    )
    today_revenue = today_agg['revenue'] or Decimal('0.00')
    today_orders = today_agg['order_count'] or 0

    trend_start = now - timedelta(days=7)
    trend_rows = (
        OrderValue.objects.filter(
            order__created_at__gte=trend_start,
        ).exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])  # H-CICLO28-01
        .annotate(day=TruncDate('order__created_at'))
        .values('day')
        .annotate(revenue=Sum('total'), orders=Count('id'))
        .order_by('day')
    )
    trend = [
        {
            'date': r['day'].isoformat() if r['day'] else None,
            'revenue': str(r['revenue'] or Decimal('0.00')),
            'orders': r['orders'],
        }
        for r in trend_rows
    ]

    top_products_rows = (
        OrderItem.objects
        .filter(order__created_at__gte=trend_start)
        .exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])  # H-CICLO28-01
        .values('product_id', 'product_name', 'sku')
        .annotate(units_sold=Sum('quantity'))
        .order_by('-units_sold')[:5]
    )
    top_products = [
        {
            'product_id': r['product_id'],
            'product_name': r['product_name'],
            'sku': r['sku'],
            'units_sold': r['units_sold'] or 0,
        }
        for r in top_products_rows
    ]

    open_tickets = SupportTicket.objects.filter(
        status__in=['OPEN', 'IN_PROGRESS', 'AWAITING_USER'],
    ).count()

    low_stock_alerts = StockAlert.objects.filter(resolved=False).count()

    return {
        'today': {
            'revenue': str(today_revenue),
            'orders': today_orders,
        },
        'trend': trend,
        'top_products': top_products,
        'open_tickets': open_tickets,
        'low_stock_alerts': low_stock_alerts,
    }


# ────────────────────────── UC-REP-04 RFM ──────────────────────────────────

def _segment(recency_days: int, frequency: int, monetary: Decimal) -> str:
    """
    Crude RFM segmentation. The UI consumes the label as a string.
    """
    if frequency >= 5 and monetary >= Decimal('5000'):
        return 'CHAMPIONS'
    if frequency >= 3:
        return 'LOYAL'
    if recency_days <= 30 and frequency >= 1:
        return 'RECENT'
    if recency_days > 90:
        return 'AT_RISK'
    return 'OCCASIONAL'


def build_rfm_payload(period_days: int, segment_filter: str | None = None) -> dict:

    start, end = period_window(period_days)
    now = timezone.now()

    rows = (
        OrderValue.objects
        .filter(
            order__created_at__gte=start, order__created_at__lte=end,
            order__user__isnull=False,
        )
        .exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])  # H-CICLO28-02
        .values(
            'order__user_id',
            user_email=F('order__user__email'),
        )
        .annotate(
            frequency=Count('order_id', distinct=True),
            monetary=Sum('total'),
            last_order_at=models_Max('order__created_at'),
        )
    )

    results = []
    total_monetary = Decimal('0.00')
    for r in rows:
        monetary = r['monetary'] or Decimal('0.00')
        last = r['last_order_at']
        recency_days = (now - last).days if last else 9999
        segment = _segment(recency_days, r['frequency'], monetary)
        if segment_filter and segment.upper() != segment_filter.upper():
            continue
        results.append({
            'user_id': r['order__user_id'],
            'email': r['user_email'],
            'recency_days': recency_days,
            'frequency': r['frequency'],
            'monetary': str(monetary),
            'segment': segment,
        })
        total_monetary += monetary

    results.sort(key=lambda x: Decimal(x['monetary']), reverse=True)

    return {
        'results': results,
        'totals': {
            'customer_count': len(results),
            'total_monetary': str(total_monetary),
        },
    }


# ────────────────────────── D-19 async threshold helper ───────────────────


def count_export_rows(slug: str, days: int) -> int:
    """Fast row count to gate the async export threshold (D-19)."""
    start, end = period_window(days)
    if slug == 'sales':
        return (
            OrderValue.objects.filter(
                order__created_at__gte=start, order__created_at__lte=end,
            ).exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT']).count()
        )
    if slug == 'top-sellers':
        return (
            OrderItem.objects
            .filter(order__created_at__gte=start, order__created_at__lte=end)
            .exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])
            .values('product_id').distinct().count()
        )
    if slug == 'customers-rfm':
        return (
            OrderValue.objects.filter(
                order__created_at__gte=start, order__created_at__lte=end,
                order__user__isnull=False,
            ).exclude(order__status__in=['CANCELLED', 'CANCELLED_TIMEOUT'])  # H-CICLO28-02
            .values('order__user_id').distinct().count()
        )
    return 0  # dashboard and unknowns are always small


# `Max` import — placed at the bottom to avoid shadowing the module-level
# `models` reference if it were used elsewhere; isolated for clarity.
