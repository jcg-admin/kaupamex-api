"""
Tests — UC-FIN-01 conciliacion de liquidaciones del gateway (GatewaySettlement).

Verifica el listado (``finance.view``) y la accion SoD ``reconcile``
(``finance.reconcile``): un usuario con ``finance.view`` pero sin la accion
nombrada NO puede conciliar.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from apps.platform.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from apps.modules.finance.models import GatewaySettlement, SettlementStatus

pytestmark = pytest.mark.integration

RECON_URL = '/api/v2/finance/reconciliations/'

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


def _settlement(ref='mp-1'):
    return GatewaySettlement.objects.create(
        adapter='mercadopago', gateway_ref=ref,
        gross=Decimal('100.00'), fee=Decimal('4.00'), net=Decimal('96.00'),
        settled_at=timezone.now(),
    )


class TestGatewaySettlementReconciliation:
    """UC-FIN-01 — conciliar liquidaciones con la accion SoD ``finance.reconcile``."""

    def test_reconciler_reconciles_settlement(self, api_client, db):
        s = _settlement('mp-recon-1')
        user = _user_with_caps('fin_recon@practicayoruba.mx',
                               ['finance.view', 'finance.reconcile'])
        api_client.force_login(user)
        res = api_client.post(f'{RECON_URL}{s.id}/reconcile/')
        assert res.status_code == 200, res.content
        assert res.data['status'] == SettlementStatus.RECONCILED
        s.refresh_from_db()
        assert s.status == SettlementStatus.RECONCILED

    def test_viewer_cannot_reconcile(self, api_client, db):
        s = _settlement('mp-recon-2')
        viewer = _user_with_caps('fin_recon_viewer@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.post(f'{RECON_URL}{s.id}/reconcile/')
        assert res.status_code == 403

    def test_viewer_lists_settlements(self, api_client, db):
        _settlement('mp-list-1')
        viewer = _user_with_caps('fin_recon_viewer2@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.get(RECON_URL)
        assert res.status_code == 200
