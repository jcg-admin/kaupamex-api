"""
Availability query — addons.finance (UC-FIN-04 disponibilidad, solo lectura).

``AvailabilityQuery`` es un **query object** (CQS: sólo consultas, sin efectos)
que deriva la disponibilidad de efectivo digital de un periodo mensual cruzando
el **percibido** conciliado (base ``settled_at``, no aprobado) contra los
**egresos**, encadenado con el **saldo previo** (último corte sellado). No es una
entidad con ciclo de vida: la "disponibilidad" es un valor derivado (UC-FIN-04
PARTE 2, "naturaleza de la operación: solo lectura").

Agrupa por **día local** en Python (``timezone.localtime``) en vez del lookup
``__date`` de la BD, que exige las tz-tables de MySQL con ``USE_TZ`` (mismo
criterio que ``_day_bounds`` en ``models``).
"""
from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from addons.base.models import SystemParameter
from addons.finance.exceptions import InvalidPeriod
from addons.finance.models import (
    CarrierInvoice, CarrierInvoiceStatus, CashClose, CashCloseStatus,
    CashConceptKind, CashMovement, GatewaySettlement, SettlementStatus,
)

#: Clave del saldo mínimo de operación (UC-FIN-04 PRE-03). Ausente => 0 (Alt C).
MINIMUM_BALANCE_PARAM = 'finance.minimum_balance'
_CENT = Decimal('0.01')


def _month_bounds(period):
    """Parsea ``YYYY-MM`` a ``[inicio, fin)`` en la tz activa (mes local).

    ``INVALID_PERIOD`` (400) si el formato es inválido o el mes está fuera de
    ``01..12`` (UC-FIN-04 EX-02).
    """
    if not isinstance(period, str) or len(period) != 7 or period[4] != '-':
        raise InvalidPeriod()
    try:
        year = int(period[:4])
        month = int(period[5:])
    except ValueError:
        raise InvalidPeriod()
    if not 1 <= month <= 12:
        raise InvalidPeriod()
    start = timezone.make_aware(datetime(year, month, 1))
    if month == 12:
        end = timezone.make_aware(datetime(year + 1, 1, 1))
    else:
        end = timezone.make_aware(datetime(year, month + 1, 1))
    return start, end


class AvailabilityQuery:
    """Deriva los KPIs, la serie caja/banco y el pivote de un periodo mensual."""

    def __init__(self, period):
        self.period = period
        self.start, self.end = _month_bounds(period)

    # ── Componentes (CQS: consultas puras) ──────────────────────────────────

    def perceived(self):
        """Percibido conciliado del periodo (Σ ``net`` de liquidaciones
        ``reconciled`` por ``settled_at``; base percibido, RNF 6.3)."""
        total = GatewaySettlement.objects.filter(
            settled_at__gte=self.start, settled_at__lt=self.end,
            status=SettlementStatus.RECONCILED,
        ).aggregate(t=Sum('net'))['t'] or Decimal('0.00')
        return total.quantize(_CENT)

    def expenses(self):
        """Egresos del periodo: fletes pagados (UC-FIN-03) + egresos de caja
        (``CashMovement`` de tipo ``expense``, p. ej. reembolsos/contracargos)."""
        freight = CarrierInvoice.objects.filter(
            paid_at__gte=self.start, paid_at__lt=self.end,
            status=CarrierInvoiceStatus.PAID,
        ).aggregate(t=Sum('gross'))['t'] or Decimal('0.00')
        cash_out = CashMovement.objects.filter(
            occurred_at__gte=self.start, occurred_at__lt=self.end,
            kind=CashConceptKind.EXPENSE,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        return (freight + cash_out).quantize(_CENT)

    def previous_balance(self):
        """Saldo previo = ``closing_balance`` del último corte **sellado** antes
        del periodo (encadenamiento con UC-FIN-02); 0 si no hay."""
        prev = CashClose.objects.filter(
            business_date__lt=self.start.date(), status=CashCloseStatus.SEALED,
        ).order_by('-business_date').first()
        return (prev.closing_balance if prev else Decimal('0.00')).quantize(_CENT)

    def minimum_balance(self):
        """Saldo mínimo parametrizado (``SystemParameter``); 0 si ausente (Alt C)."""
        raw = SystemParameter.get_param(MINIMUM_BALANCE_PARAM)
        return (Decimal(str(raw)) if raw is not None else Decimal('0.00')).quantize(_CENT)

    def provisional(self):
        """¿Hay percibido sin conciliar en el periodo? (EX-04): la
        disponibilidad es provisional hasta cerrar la conciliación."""
        return GatewaySettlement.objects.filter(
            settled_at__gte=self.start, settled_at__lt=self.end,
        ).exclude(status=SettlementStatus.RECONCILED).exists()

    def _has_movements(self):
        return (
            GatewaySettlement.objects.filter(
                settled_at__gte=self.start, settled_at__lt=self.end).exists()
            or CashMovement.objects.filter(
                occurred_at__gte=self.start, occurred_at__lt=self.end).exists()
        )

    # ── Salidas (dicts JSON-ready: dinero como string decimal) ───────────────

    def kpis(self):
        """KPIs del periodo (UC-FIN-04 PARTE 7.2): percibido, egresos, saldo
        actual, saldo mínimo, semáforo ``surplus``/``deficit`` y flags."""
        perceived = self.perceived()
        expenses = self.expenses()
        minimum = self.minimum_balance()
        current = (self.previous_balance() + perceived - expenses).quantize(_CENT)
        status = 'surplus' if current >= minimum else 'deficit'
        return {
            'period': self.period,
            'perceived': str(perceived),
            'expenses': str(expenses),
            'current_balance': str(current),
            'minimum_balance': str(minimum),
            'status': status,
            'provisional': self.provisional(),
            'empty': not self._has_movements(),
        }

    def series(self):
        """Serie diaria caja vs banco (UC-FIN-04 paso 4 / AC-06).

        ``bank`` = neto conciliado liberado ese día (``settled_at`` local);
        ``cash`` = ingresos de caja (``CashMovement`` income) ese día. Agrupa por
        día local en Python (sin lookup ``__date``). Serie dispersa: sólo días
        con actividad.
        """
        buckets = {}
        settlements = GatewaySettlement.objects.filter(
            settled_at__gte=self.start, settled_at__lt=self.end,
            status=SettlementStatus.RECONCILED,
        ).values_list('settled_at', 'net')
        for settled_at, net in settlements:
            day = timezone.localtime(settled_at).date().isoformat()
            b = buckets.setdefault(day, {'cash': Decimal('0.00'), 'bank': Decimal('0.00')})
            b['bank'] += net
        movements = CashMovement.objects.filter(
            occurred_at__gte=self.start, occurred_at__lt=self.end,
            kind=CashConceptKind.INCOME,
        ).values_list('occurred_at', 'amount')
        for occurred_at, amount in movements:
            day = timezone.localtime(occurred_at).date().isoformat()
            b = buckets.setdefault(day, {'cash': Decimal('0.00'), 'bank': Decimal('0.00')})
            b['cash'] += amount
        return {
            'period': self.period,
            'series': [
                {'date': day, 'cash': str(v['cash'].quantize(_CENT)),
                 'bank': str(v['bank'].quantize(_CENT))}
                for day, v in sorted(buckets.items())
            ],
        }

    def pivot(self):
        """Pivote concepto x periodo (UC-FIN-04 paso 5): importes de
        ``CashMovement`` agregados por concepto."""
        rows = (
            CashMovement.objects.filter(
                occurred_at__gte=self.start, occurred_at__lt=self.end,
            )
            .values('concept__code', 'kind')
            .annotate(total=Sum('amount'))
            .order_by('concept__code')
        )
        return {
            'period': self.period,
            'pivot': [
                {'concept': r['concept__code'], 'kind': r['kind'],
                 'total': str((r['total'] or Decimal('0.00')).quantize(_CENT))}
                for r in rows
            ],
        }
