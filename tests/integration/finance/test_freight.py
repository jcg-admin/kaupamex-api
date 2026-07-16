"""
Tests — UC-FIN-03 flete por pagar al transportista (CarrierInvoice).

Registrar y pagar el flete exigen la accion SoD ``finance.disburse``
(salida de dinero); listar/ver basta ``finance.view``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model

import pytest

from apps.platform.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from apps.modules.finance.models import CarrierInvoice, CarrierInvoiceStatus

pytestmark = pytest.mark.integration

FREIGHT_URL = '/api/v2/finance/carrier-invoices/'

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


class TestCarrierInvoice:
    """UC-FIN-03 — flete por pagar con la accion SoD ``finance.disburse``."""

    def test_disburser_registers_freight(self, api_client, db):
        user = _user_with_caps('fin_disb@practicayoruba.mx', ['finance.disburse'])
        api_client.force_login(user)
        res = api_client.post(FREIGHT_URL, {
            'carrier': 'Estafeta', 'gross': '120.00',
            'free_shipping_subsidy': '30.00',
        }, format='json')
        assert res.status_code == 201, res.content
        assert res.data['status'] == CarrierInvoiceStatus.PAYABLE

    def test_viewer_cannot_register(self, api_client, db):
        viewer = _user_with_caps('fin_disb_viewer@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.post(FREIGHT_URL, {'carrier': 'DHL', 'gross': '80.00'}, format='json')
        assert res.status_code == 403

    def test_disburser_pays_freight(self, api_client, db):
        inv = CarrierInvoice.objects.create(carrier='FedEx', gross=Decimal('90.00'))
        user = _user_with_caps('fin_disb2@practicayoruba.mx', ['finance.disburse'])
        api_client.force_login(user)
        res = api_client.post(f'{FREIGHT_URL}{inv.id}/pay/')
        assert res.status_code == 200, res.content
        assert res.data['status'] == CarrierInvoiceStatus.PAID
        inv.refresh_from_db()
        assert inv.status == CarrierInvoiceStatus.PAID
        assert inv.paid_at is not None

    def test_viewer_cannot_pay(self, api_client, db):
        inv = CarrierInvoice.objects.create(carrier='UPS', gross=Decimal('75.00'))
        viewer = _user_with_caps('fin_disb_viewer2@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.post(f'{FREIGHT_URL}{inv.id}/pay/')
        assert res.status_code == 403

    def test_viewer_lists_freight(self, api_client, db):
        CarrierInvoice.objects.create(carrier='Estafeta', gross=Decimal('50.00'))
        viewer = _user_with_caps('fin_disb_viewer3@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.get(FREIGHT_URL)
        assert res.status_code == 200
