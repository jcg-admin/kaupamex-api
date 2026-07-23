"""
Tests — UC-FIN-04 disponibilidad (caja vs banco), consulta de solo lectura.

Query de agregación (sin máquina de estados): percibido conciliado (base
``settled_at``) − egresos (fletes pagados + egresos de caja) + saldo previo
(último corte sellado). Semáforo ``surplus``/``deficit`` contra el saldo mínimo
parametrizado (``SystemParameter finance.minimum_balance``, Alt C default 0).
Todo ``GET``; gateado por ``finance.view``. Códigos: ``INVALID_PERIOD`` (400),
``FORBIDDEN`` (403).
"""
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from addons.base.models import SystemParameter
from addons.finance.models import (
    CarrierInvoice, CarrierInvoiceStatus, CashClose, CashCloseStatus, CashConcept,
    CashConceptKind, CashMovement, GatewaySettlement, SettlementStatus,
)

pytestmark = pytest.mark.integration

AV_URL = '/api/v2/finance/availability/'

_VERB_LEVEL = {
    'view': AccessLevel.VIEW, 'create': AccessLevel.CREATE,
    'edit': AccessLevel.EDIT, 'full': AccessLevel.FULL,
}


def _user_with_caps(email, codes):
    role, _ = Role.objects.get_or_create(
        code=f'role_{"_".join(c.replace(".", "_") for c in codes)}',
        defaults={'name': 'Test finance role'},
    )
    for code in codes:
        noun, _, verb = code.partition('.')
        if verb in _VERB_LEVEL:
            target, level = noun, _VERB_LEVEL[verb]
        else:
            target, level = code, AccessLevel.FULL
        module, _ = Module.objects.get_or_create(
            code=target.split('.', 1)[0], defaults={'name': target},
        )
        cap, _ = Capability.objects.get_or_create(
            code=target, defaults={'module': module, 'name': target},
        )
        RoleCapability.objects.update_or_create(
            role=role, capability=cap, defaults={'level': level},
        )
    user = get_user_model().objects.create_user(email=email, password='TestPass123!')
    RoleAssignment.objects.create(user=user, role=role)
    return user


def _viewer(email='fin_v@practicayoruba.mx'):
    return _user_with_caps(email, ['finance.view'])


def _at(y, m, d, h=10):
    return timezone.make_aware(datetime(y, m, d, h, 0))


class TestAvailabilityKpis:
    """UC-FIN-04 PARTE 3 + 7B — KPIs de disponibilidad."""

    def test_current_balance_is_perceived_minus_expenses(self, api_client, db):
        # AC-01: percibido 500 - egreso 120 + saldo previo 0 = 380.
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-A-1',
            gross=Decimal('520'), fee=Decimal('20'), net=Decimal('500'),
            settled_at=_at(2026, 7, 10), status=SettlementStatus.RECONCILED,
        )
        CarrierInvoice.objects.create(
            carrier='dhl', gross=Decimal('120'),
            status=CarrierInvoiceStatus.PAID, paid_at=_at(2026, 7, 12),
        )
        api_client.force_login(_viewer())
        res = api_client.get(AV_URL, {'period': '2026-07'})
        assert res.status_code == 200, res.content
        assert Decimal(res.data['perceived']) == Decimal('500.00')
        assert Decimal(res.data['expenses']) == Decimal('120.00')
        assert Decimal(res.data['current_balance']) == Decimal('380.00')
        assert res.data['status'] == 'surplus'

    def test_previous_balance_chains_from_sealed_cash_close(self, api_client, db):
        # Saldo previo = closing del último corte sellado antes del periodo.
        CashClose.objects.create(
            business_date='2026-06-30', status=CashCloseStatus.SEALED,
            closing_balance=Decimal('1000.00'), sealed_at=timezone.now(),
        )
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-B-1',
            gross=Decimal('210'), fee=Decimal('10'), net=Decimal('200'),
            settled_at=_at(2026, 7, 5), status=SettlementStatus.RECONCILED,
        )
        api_client.force_login(_viewer())
        res = api_client.get(AV_URL, {'period': '2026-07'})
        assert res.status_code == 200, res.content
        # 1000 previo + 200 percibido - 0 egresos = 1200.
        assert Decimal(res.data['current_balance']) == Decimal('1200.00')

    def test_deficit_when_below_minimum(self, api_client, db):
        # AC-02: saldo actual < mínimo -> deficit.
        SystemParameter.set_param('finance.minimum_balance', '5000')
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-D-1',
            gross=Decimal('110'), fee=Decimal('10'), net=Decimal('100'),
            settled_at=_at(2026, 7, 3), status=SettlementStatus.RECONCILED,
        )
        api_client.force_login(_viewer())
        res = api_client.get(AV_URL, {'period': '2026-07'})
        assert res.status_code == 200, res.content
        assert Decimal(res.data['minimum_balance']) == Decimal('5000.00')
        assert res.data['status'] == 'deficit'

    def test_empty_period_returns_zeros(self, api_client, db):
        # AC-03: periodo sin movimientos -> 200, ceros, empty=True (no error).
        api_client.force_login(_viewer())
        res = api_client.get(AV_URL, {'period': '2026-07'})
        assert res.status_code == 200, res.content
        assert Decimal(res.data['perceived']) == Decimal('0.00')
        assert Decimal(res.data['current_balance']) == Decimal('0.00')
        assert res.data['empty'] is True

    def test_provisional_when_pending_settlements(self, api_client, db):
        # AC-04: cobros sin conciliar en el periodo -> provisional=True.
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-P-1',
            gross=Decimal('100'), fee=Decimal('3'), net=Decimal('97'),
            settled_at=_at(2026, 7, 4), status=SettlementStatus.IMPORTED,
        )
        api_client.force_login(_viewer())
        res = api_client.get(AV_URL, {'period': '2026-07'})
        assert res.status_code == 200, res.content
        assert res.data['provisional'] is True

    def test_invalid_period_400(self, api_client, db):
        # EX-02: periodo mal formado -> INVALID_PERIOD.
        api_client.force_login(_viewer())
        res = api_client.get(AV_URL, {'period': '2026-13'})
        assert res.status_code == 400, res.content
        assert res.data['codigo_error'] == 'INVALID_PERIOD'

    def test_missing_capability_403(self, api_client, db):
        # AC-05: sin finance.view -> 403.
        api_client.force_login(_user_with_caps('nofin@practicayoruba.mx', ['catalogue.view']))
        res = api_client.get(AV_URL, {'period': '2026-07'})
        assert res.status_code == 403, res.content


class TestAvailabilitySeries:
    """UC-FIN-04 paso 4 + AC-06 — serie diaria caja vs banco."""

    def test_series_splits_cash_and_bank_by_settled_at(self, api_client, db):
        # AC-06: banco = neto conciliado del día (settled_at); caja = ingresos
        # de CashMovement del día.
        concept = CashConcept.objects.create(
            code='SALES', name='Ventas', kind=CashConceptKind.INCOME,
        )
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-SER-1',
            gross=Decimal('330'), fee=Decimal('30'), net=Decimal('300'),
            settled_at=_at(2026, 7, 8), status=SettlementStatus.RECONCILED,
        )
        CashMovement.objects.create(
            concept=concept, kind=CashConceptKind.INCOME, amount=Decimal('75'),
            occurred_at=_at(2026, 7, 8),
        )
        api_client.force_login(_viewer())
        res = api_client.get(f'{AV_URL}series/', {'period': '2026-07'})
        assert res.status_code == 200, res.content
        day = next(r for r in res.data['series'] if r['date'] == '2026-07-08')
        assert Decimal(day['bank']) == Decimal('300.00')
        assert Decimal(day['cash']) == Decimal('75.00')


class TestAvailabilityPivot:
    """UC-FIN-04 paso 5 — pivote concepto x periodo."""

    def test_pivot_aggregates_by_concept(self, api_client, db):
        concept = CashConcept.objects.create(
            code='FREIGHT_OUT', name='Flete', kind=CashConceptKind.EXPENSE,
        )
        for amt in ('40', '60'):
            CashMovement.objects.create(
                concept=concept, kind=CashConceptKind.EXPENSE, amount=Decimal(amt),
                occurred_at=_at(2026, 7, 9),
            )
        api_client.force_login(_viewer())
        res = api_client.get(f'{AV_URL}pivot/', {'period': '2026-07'})
        assert res.status_code == 200, res.content
        row = next(r for r in res.data['pivot'] if r['concept'] == 'FREIGHT_OUT')
        assert Decimal(row['total']) == Decimal('100.00')
        assert row['kind'] == CashConceptKind.EXPENSE
