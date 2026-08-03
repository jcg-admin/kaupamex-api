"""L0 tariff catalog API — ``/api/v2/platform/module-prices/`` (S4 / #180).

El operador Kaupamex siembra/gestiona las tarifas por módulo × ciclo
(``ModulePrice``) desde la consola L0. Least-privilege por acción: lectura
``platform.view``, escritura ``platform.provision`` (misma regla que las
suscripciones). Es la contraparte del price-copy: sin tarifas sembradas, una
suscripción se contrata sin precio (free); con tarifa vigente, la copia la
congela.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from addons.authz.models import Capability, Module, Role, RoleAssignment
from addons.sale_subscription.models import (
    ModulePrice,
)

pytestmark = pytest.mark.integration

PRICES_URL = '/api/v2/platform/module-prices/'


def _user_with_caps(email, codes):
    caps = []
    for code in codes:
        domain = code.split('.', 1)[0]
        module, _ = Module.objects.get_or_create(code=domain, defaults={'name': domain})
        cap, _ = Capability.objects.get_or_create(
            code=code, defaults={'module': module, 'name': code},
        )
        caps.append(cap)
    role, _ = Role.objects.get_or_create(
        code=f'role_{"_".join(c.replace(".", "_") for c in codes)}',
        defaults={'name': 'Test platform role'},
    )
    role.capabilities.set(caps)
    u = get_user_model().objects.create_user(login=email, password='TestPass123!')
    RoleAssignment.objects.create(user=u, role=role)
    return u


class TestModulePricesApi:
    def test_operator_seeds_a_tariff(self, api_client, db):
        m = Module.objects.create(code='catalogue', name='Catálogo')
        operator = _user_with_caps('l0_pset@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(PRICES_URL, {
            'module': m.pk, 'billing_cycle': 'monthly', 'price': '199.00',
            'effective_from': (timezone.now() - timedelta(days=1)).isoformat(),
        }, format='json')
        assert res.status_code == 201, res.data
        assert ModulePrice.objects.filter(module=m, price=Decimal('199.00')).exists()

    def test_reader_can_list_tariffs(self, api_client, db):
        m = Module.objects.create(code='catalogue', name='Catálogo')
        ModulePrice.objects.create(
            module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
            price=Decimal('199.00'), effective_from=timezone.now() - timedelta(days=1),
        )
        reader = _user_with_caps('l0_pread@practicayoruba.mx', ['platform.view'])
        api_client.force_login(reader)
        res = api_client.get(PRICES_URL)
        assert res.status_code == 200
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        assert len(rows) == 1
        assert rows[0]['module_code'] == 'catalogue'
        assert rows[0]['price'] == '199.00'

    def test_reader_cannot_write(self, api_client, db):
        m = Module.objects.create(code='catalogue', name='Catálogo')
        reader = _user_with_caps('l0_prw@practicayoruba.mx', ['platform.view'])
        api_client.force_login(reader)
        res = api_client.post(PRICES_URL, {
            'module': m.pk, 'billing_cycle': 'monthly', 'price': '9.00',
            'effective_from': timezone.now().isoformat(),
        }, format='json')
        assert res.status_code == 403

    def test_anonymous_denied(self, api_client, db):
        res = api_client.get(PRICES_URL)
        assert res.status_code in (401, 403)
