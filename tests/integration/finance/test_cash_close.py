"""
Tests — UC-FIN-02 corte de caja diario (CashClose).

Maquina de estados ``open -> balanced -> sealed -> reopened`` con SoD
(``prepared_by`` != ``approved_by``). Preparar/arquear = ``finance.record``;
aprobar/sellar/reabrir = ``finance.close`` (accion SoD). Codigos de error
canonicos (UC-FIN-02 PARTE 5): ``SOD_VIOLATION``, ``CASH_CLOSE_SEALED``,
``SETTLEMENTS_NOT_RECONCILED``, ``CASH_CLOSE_ALREADY_OPEN``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from apps.platform.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from apps.addons.finance.models import (
    CashClose, CashCloseStatus, GatewaySettlement, SettlementStatus,
)

pytestmark = pytest.mark.integration

CLOSE_URL = '/api/v2/finance/cash-closes/'

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


def _preparer(email='fin_prep@practicayoruba.mx'):
    return _user_with_caps(email, ['finance.record'])


def _approver(email='fin_appr@practicayoruba.mx'):
    return _user_with_caps(email, ['finance.close'])


class TestCashCloseLifecycle:
    """UC-FIN-02 — flujo principal open -> balanced -> sealed."""

    def test_preparer_creates_open_close(self, api_client, db):
        api_client.force_login(_preparer())
        res = api_client.post(CLOSE_URL, {
            'business_date': '2026-07-17', 'opening_balance': '100.00',
        }, format='json')
        assert res.status_code == 201, res.content
        assert res.data['status'] == CashCloseStatus.OPEN
        assert res.data['prepared_by'] is not None

    def test_viewer_cannot_create(self, api_client, db):
        api_client.force_login(_user_with_caps('fin_v@practicayoruba.mx', ['finance.view']))
        res = api_client.post(CLOSE_URL, {'business_date': '2026-07-17'}, format='json')
        assert res.status_code == 403

    def test_arqueo_balances_and_computes_discrepancy(self, api_client, db):
        api_client.force_login(_preparer())
        close = CashClose.objects.create(
            business_date='2026-07-17', opening_balance=Decimal('100.00'),
        )
        # Sin liquidaciones/egresos ese dia -> esperado = opening (100). Contado
        # 112 -> discrepancy 12.
        res = api_client.post(f'{CLOSE_URL}{close.id}/arqueo/',
                              {'counted_balance': '112.00'}, format='json')
        assert res.status_code == 200, res.content
        assert res.data['status'] == CashCloseStatus.BALANCED
        assert Decimal(res.data['closing_balance']) == Decimal('112.00')
        assert Decimal(res.data['discrepancy']) == Decimal('12.00')


class TestCashCloseSoD:
    """UC-FIN-02 PARTE 5 EX-01 — segregacion de funciones."""

    def test_same_user_cannot_approve_own_close(self, api_client, db):
        # Un usuario con ambas capacidades prepara y luego intenta aprobar.
        both = _user_with_caps('fin_both@practicayoruba.mx',
                               ['finance.record', 'finance.close'])
        close = CashClose.objects.create(
            business_date='2026-07-17', status=CashCloseStatus.BALANCED,
            prepared_by=both,
        )
        api_client.force_login(both)
        res = api_client.post(f'{CLOSE_URL}{close.id}/approve/', {}, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'SOD_VIOLATION'
        close.refresh_from_db()
        assert close.approved_by_id is None

    def test_second_user_approves(self, api_client, db):
        preparer = _preparer()
        close = CashClose.objects.create(
            business_date='2026-07-17', status=CashCloseStatus.BALANCED,
            prepared_by=preparer,
        )
        api_client.force_login(_approver())
        res = api_client.post(f'{CLOSE_URL}{close.id}/approve/',
                              {'note': 'Diferencia por redondeo'}, format='json')
        assert res.status_code == 200, res.content
        close.refresh_from_db()
        assert close.approved_by is not None
        assert close.note == 'Diferencia por redondeo'


class TestCashCloseSeal:
    """UC-FIN-02 PARTE 5 EX-02/EX-03 — sello, inmutabilidad, conciliacion."""

    def _approved_close(self, preparer, approver):
        close = CashClose.objects.create(
            business_date='2026-07-17', status=CashCloseStatus.BALANCED,
            prepared_by=preparer, approved_by=approver,
        )
        return close

    def test_seal_blocked_if_settlements_not_reconciled(self, api_client, db):
        close = self._approved_close(_preparer(), _approver())
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-NR-1',
            gross=Decimal('100'), fee=Decimal('3'), net=Decimal('97'),
            settled_at=timezone.make_aware(timezone.datetime(2026, 7, 17, 10, 0)),
            status=SettlementStatus.IMPORTED,
        )
        api_client.force_login(_approver('fin_sealer@practicayoruba.mx'))
        res = api_client.post(f'{CLOSE_URL}{close.id}/seal/', {}, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'SETTLEMENTS_NOT_RECONCILED'

    def test_seal_succeeds_when_reconciled(self, api_client, db):
        close = self._approved_close(_preparer(), _approver())
        GatewaySettlement.objects.create(
            adapter='mercadopago', gateway_ref='S-R-1',
            gross=Decimal('100'), fee=Decimal('3'), net=Decimal('97'),
            settled_at=timezone.make_aware(timezone.datetime(2026, 7, 17, 10, 0)),
            status=SettlementStatus.RECONCILED,
        )
        api_client.force_login(_approver('fin_sealer2@practicayoruba.mx'))
        res = api_client.post(f'{CLOSE_URL}{close.id}/seal/', {}, format='json')
        assert res.status_code == 200, res.content
        assert res.data['status'] == CashCloseStatus.SEALED
        close.refresh_from_db()
        assert close.sealed_at is not None

    def test_cannot_seal_without_approval(self, api_client, db):
        # Un corte balanced sin approved_by no puede sellarse (SoD sin aprobador).
        close = CashClose.objects.create(
            business_date='2026-07-17', status=CashCloseStatus.BALANCED,
            prepared_by=_preparer(),
        )
        api_client.force_login(_approver('fin_sealer3@practicayoruba.mx'))
        res = api_client.post(f'{CLOSE_URL}{close.id}/seal/', {}, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'SOD_VIOLATION'

    def test_sealed_close_is_immutable(self, api_client, db):
        close = CashClose.objects.create(
            business_date='2026-07-17', status=CashCloseStatus.SEALED,
            prepared_by=_preparer(), approved_by=_approver(),
            sealed_at=timezone.now(),
        )
        api_client.force_login(_approver('fin_sealer4@practicayoruba.mx'))
        res = api_client.post(f'{CLOSE_URL}{close.id}/seal/', {}, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'CASH_CLOSE_SEALED'


class TestCashCloseGuards:
    """UC-FIN-02 PARTE 5 EX-06 (colision) + Alt B (reapertura)."""

    def test_duplicate_unsealed_close_rejected(self, api_client, db):
        CashClose.objects.create(
            business_date='2026-07-17', status=CashCloseStatus.OPEN,
            prepared_by=_preparer('fin_p1@practicayoruba.mx'),
        )
        api_client.force_login(_preparer('fin_p2@practicayoruba.mx'))
        res = api_client.post(CLOSE_URL, {'business_date': '2026-07-17'}, format='json')
        assert res.status_code == 409, res.content
        assert res.data['codigo_error'] == 'CASH_CLOSE_ALREADY_OPEN'

    def test_new_close_allowed_when_prior_is_sealed(self, api_client, db):
        CashClose.objects.create(
            business_date='2026-07-16', status=CashCloseStatus.SEALED,
            prepared_by=_preparer('fin_p3@practicayoruba.mx'),
            approved_by=_approver('fin_a3@practicayoruba.mx'),
            sealed_at=timezone.now(),
        )
        api_client.force_login(_preparer('fin_p4@practicayoruba.mx'))
        res = api_client.post(CLOSE_URL, {'business_date': '2026-07-16'}, format='json')
        assert res.status_code == 201, res.content

    def test_reopen_sealed_close(self, api_client, db):
        close = CashClose.objects.create(
            business_date='2026-07-17', status=CashCloseStatus.SEALED,
            prepared_by=_preparer(), approved_by=_approver(),
            sealed_at=timezone.now(),
        )
        api_client.force_login(_approver('fin_reopener@practicayoruba.mx'))
        res = api_client.post(f'{CLOSE_URL}{close.id}/reopen/',
                              {'reason': 'Correccion de comision'}, format='json')
        assert res.status_code == 200, res.content
        assert res.data['status'] == CashCloseStatus.REOPENED
        close.refresh_from_db()
        assert close.reopen_reason == 'Correccion de comision'

    def test_viewer_lists_closes(self, api_client, db):
        CashClose.objects.create(business_date='2026-07-17', prepared_by=_preparer())
        api_client.force_login(_user_with_caps('fin_v2@practicayoruba.mx', ['finance.view']))
        res = api_client.get(CLOSE_URL)
        assert res.status_code == 200
