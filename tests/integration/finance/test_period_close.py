"""
Tests — UC-FIN-08 cierre de ejercicio anual (PeriodClose).

Maquina de estados ``open <-> sealed``. Ver = ``finance.view``; cerrar/reabrir =
``finance.close`` (accion SoD FULL + reautenticacion DEC-12, gateada por la capa
authz). El cierre es **sellante y transaccional**: congela el ``closing_balance``
(saldo final percibido) y abre el ejercicio siguiente con ese saldo como
``opening_balance`` (encadenamiento anual). Codigos de error canonicos
(UC-FIN-08 PARTE 5): ``OPEN_MOVEMENTS``, ``OUT_OF_ORDER_CLOSE``,
``INVALID_STATE``, ``BACKUP_REQUIRED``, ``FORBIDDEN``.
"""
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from addons.finance.models import (
    CashClose, CashCloseStatus, GatewaySettlement, PeriodClose,
    PeriodCloseStatus, SettlementStatus,
)

pytestmark = pytest.mark.integration

PC_URL = '/api/v2/finance/period-closes/'

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


def _closer(email='fin_closer@practicayoruba.mx'):
    return _user_with_caps(email, ['finance.close'])


def _in_year(year, month=6, day=15, hour=10):
    """DateTime aware dentro del ejercicio ``year`` (para movimientos)."""
    return timezone.make_aware(datetime(year, month, day, hour, 0))


class TestPeriodCloseView:
    """UC-FIN-08 — ver estado de ejercicios (``finance.view``)."""

    def test_viewer_lists_periods(self, api_client, db):
        PeriodClose.objects.create(fiscal_year=2025, status=PeriodCloseStatus.SEALED)
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        api_client.force_login(_user_with_caps('fin_v@practicayoruba.mx', ['finance.view']))
        res = api_client.get(PC_URL)
        assert res.status_code == 200, res.content
        years = {row['fiscal_year'] for row in res.data}
        assert years == {2025, 2026}

    def test_close_action_is_named_not_graded(self, api_client, db):
        # DEC-11: finance.close es una accion SoD NOMBRADA, no el sustantivo
        # graduado finance -> NO implica finance.view. Un actor con solo
        # finance.close no puede LISTAR (ver exige finance VIEW, aditivo).
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        api_client.force_login(_closer())
        res = api_client.get(PC_URL)
        assert res.status_code == 403, res.content

    def test_actor_with_both_caps_lists(self, api_client, db):
        # El actor real de UC-FIN-08 tiene finance VIEW (ver) + finance.close
        # (cerrar), aditivos: puede listar.
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        api_client.force_login(_user_with_caps(
            'fin_both@practicayoruba.mx', ['finance.view', 'finance.close']))
        res = api_client.get(PC_URL)
        assert res.status_code == 200, res.content


class TestPeriodCloseSeal:
    """UC-FIN-08 PARTE 3 + 7B — cierre sellante y encadenamiento anual."""

    def test_close_seals_and_opens_next_year(self, api_client, db):
        # AC-01: ejercicio open, sin pendientes, con backup -> sealed + siguiente.
        PeriodClose.objects.create(
            fiscal_year=2026, status=PeriodCloseStatus.OPEN,
            opening_balance=Decimal('1000.00'),
        )
        # Un ingreso conciliado del ejercicio -> closing = 1000 + 500 = 1500.
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-2026-1',
            gross=Decimal('520'), fee=Decimal('20'), net=Decimal('500'),
            settled_at=_in_year(2026), status=SettlementStatus.RECONCILED,
        )
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/close/', {
            'idempotency_key': 'close-fy2026-a', 'backup_confirmed': True,
        }, format='json')
        assert res.status_code == 200, res.content
        assert res.data['sealed']['status'] == PeriodCloseStatus.SEALED
        assert Decimal(res.data['sealed']['closing_balance']) == Decimal('1500.00')
        assert res.data['next']['fiscal_year'] == 2027
        assert res.data['next']['status'] == PeriodCloseStatus.OPEN
        assert Decimal(res.data['next']['opening_balance']) == Decimal('1500.00')
        # Estado persistido.
        assert PeriodClose.objects.get(fiscal_year=2026).status == PeriodCloseStatus.SEALED
        assert PeriodClose.objects.get(fiscal_year=2027).status == PeriodCloseStatus.OPEN

    def test_close_blocked_by_pending_settlement(self, api_client, db):
        # AC-02: liquidacion sin conciliar en el ejercicio -> OPEN_MOVEMENTS.
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-2026-P',
            gross=Decimal('100'), fee=Decimal('3'), net=Decimal('97'),
            settled_at=_in_year(2026), status=SettlementStatus.IMPORTED,
        )
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/close/', {
            'idempotency_key': 'k', 'backup_confirmed': True,
        }, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'OPEN_MOVEMENTS'
        assert PeriodClose.objects.get(fiscal_year=2026).status == PeriodCloseStatus.OPEN

    def test_close_blocked_by_unsealed_cash_close(self, api_client, db):
        # AC-02: corte de caja sin sellar dentro del ejercicio -> OPEN_MOVEMENTS.
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        CashClose.objects.create(
            business_date='2026-06-15', status=CashCloseStatus.OPEN,
        )
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/close/', {
            'idempotency_key': 'k', 'backup_confirmed': True,
        }, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'OPEN_MOVEMENTS'

    def test_close_out_of_order_blocked(self, api_client, db):
        # AC-03: un ejercicio anterior aun open -> OUT_OF_ORDER_CLOSE.
        PeriodClose.objects.create(fiscal_year=2025, status=PeriodCloseStatus.OPEN)
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/close/', {
            'idempotency_key': 'k', 'backup_confirmed': True,
        }, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'OUT_OF_ORDER_CLOSE'

    def test_close_requires_backup(self, api_client, db):
        # EX-07: sin backup_confirmed -> BACKUP_REQUIRED.
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/close/', {
            'idempotency_key': 'k',
        }, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'BACKUP_REQUIRED'
        assert PeriodClose.objects.get(fiscal_year=2026).status == PeriodCloseStatus.OPEN

    def test_close_idempotent_retry(self, api_client, db):
        # AC-04 / Alt C: reintento con el mismo key no duplica el siguiente.
        PeriodClose.objects.create(
            fiscal_year=2026, status=PeriodCloseStatus.OPEN,
            opening_balance=Decimal('200.00'),
        )
        api_client.force_login(_closer())
        body = {'idempotency_key': 'close-fy2026-once', 'backup_confirmed': True}
        first = api_client.post(f'{PC_URL}2026/close/', body, format='json')
        assert first.status_code == 200, first.content
        second = api_client.post(f'{PC_URL}2026/close/', body, format='json')
        assert second.status_code == 200, second.content
        # No se crea un segundo 2027; sigue habiendo exactamente un 2027.
        assert PeriodClose.objects.filter(fiscal_year=2027).count() == 1
        assert second.data['sealed']['closing_balance'] == first.data['sealed']['closing_balance']

    def test_close_already_sealed_invalid_state(self, api_client, db):
        # EX-05: cerrar un ejercicio ya sealed con OTRO key -> INVALID_STATE.
        PeriodClose.objects.create(
            fiscal_year=2026, status=PeriodCloseStatus.SEALED,
            closing_balance=Decimal('10.00'), idempotency_key='orig',
            sealed_at=timezone.now(),
        )
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/close/', {
            'idempotency_key': 'distinto', 'backup_confirmed': True,
        }, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'INVALID_STATE'

    def test_viewer_cannot_close(self, api_client, db):
        # AC-05: sin finance.close -> 403; ver sigue disponible.
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        api_client.force_login(_user_with_caps('fin_v3@practicayoruba.mx', ['finance.view']))
        res = api_client.post(f'{PC_URL}2026/close/', {
            'idempotency_key': 'k', 'backup_confirmed': True,
        }, format='json')
        assert res.status_code == 403, res.content
        assert PeriodClose.objects.get(fiscal_year=2026).status == PeriodCloseStatus.OPEN


class TestPeriodCloseReopen:
    """UC-FIN-08 PARTE 4 Alt B — reapertura de alto control."""

    def test_reopen_sealed_year_stales_next(self, api_client, db):
        # AC-07: reabrir un sealed -> open; el siguiente queda opening_balance_stale.
        PeriodClose.objects.create(
            fiscal_year=2026, status=PeriodCloseStatus.SEALED,
            closing_balance=Decimal('500.00'), sealed_at=timezone.now(),
        )
        PeriodClose.objects.create(
            fiscal_year=2027, status=PeriodCloseStatus.OPEN,
            opening_balance=Decimal('500.00'),
        )
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/reopen/', {
            'reason': 'Comision omitida en Q4',
        }, format='json')
        assert res.status_code == 200, res.content
        assert res.data['status'] == PeriodCloseStatus.OPEN
        reopened = PeriodClose.objects.get(fiscal_year=2026)
        assert reopened.reopen_reason == 'Comision omitida en Q4'
        assert reopened.reopened_at is not None
        assert PeriodClose.objects.get(fiscal_year=2027).opening_balance_stale is True

    def test_reopen_open_year_invalid_state(self, api_client, db):
        # EX-05: reabrir un ejercicio ya open -> INVALID_STATE.
        PeriodClose.objects.create(fiscal_year=2026, status=PeriodCloseStatus.OPEN)
        api_client.force_login(_closer())
        res = api_client.post(f'{PC_URL}2026/reopen/', {
            'reason': 'no aplica',
        }, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'INVALID_STATE'
