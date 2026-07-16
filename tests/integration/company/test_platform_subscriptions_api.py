"""Tests — L0 platform module-subscription API (SOL-085 S4, CRUD).

``/api/v2/platform/module-subscriptions/`` es la contraparte API del mockup
"asignar módulos a companies": el operador Kaupamex (L0) contrata/gestiona qué
``Module`` tiene activo cada ``Company``. Scope por acción (least-privilege):
lectura ``platform.view``, escritura ``platform.provision``. El guard de
dependencias S3 (``CompanyModuleSubscription.save()``) se superficializa como
400, no como 500.
"""
from django.contrib.auth import get_user_model

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.platform.authz.models import Capability, Module, Role, RoleAssignment
from apps.platform.company.models import (
    Company,
    CompanyModuleSubscription,
    ModulePrice,
)

import pytest

pytestmark = pytest.mark.integration

SUBS_URL = '/api/v2/platform/module-subscriptions/'


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
    u = get_user_model().objects.create_user(email=email, password='TestPass123!')
    RoleAssignment.objects.create(user=u, role=role)
    return u


class TestPlatformSubscriptionsGate:
    def test_operator_can_assign_a_module(self, api_client, db):
        company = Company.objects.create(code='acme', name='Acme')
        cat = Module.objects.create(code='catalogue', name='Catálogo')
        operator = _user_with_caps('l0_prov@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(SUBS_URL, {
            'company': company.pk, 'module': cat.pk, 'status': 'active',
        }, format='json')
        assert res.status_code == 201, res.data
        assert company.active_module_codes() == {'catalogue'}

    def test_subscribe_copies_current_price_from_catalog(self, api_client, db):
        """Al contratar, ``price`` se copia del ``ModulePrice`` vigente según el
        ``billing_cycle`` enviado; el cliente NO fija ``price`` (read-only)."""
        company = Company.objects.create(code='acme', name='Acme')
        cat = Module.objects.create(code='catalogue', name='Catálogo')
        ModulePrice.objects.create(
            module=cat, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
            price=Decimal('199.00'),
            effective_from=timezone.now() - timedelta(days=1),
        )
        operator = _user_with_caps('l0_price@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(SUBS_URL, {
            'company': company.pk, 'module': cat.pk, 'status': 'active',
            'billing_cycle': 'monthly', 'price': '9999.00',  # ignorado (read-only)
        }, format='json')
        assert res.status_code == 201, res.data
        sub = CompanyModuleSubscription.objects.get(company=company, module=cat)
        assert sub.price == Decimal('199.00')
        assert sub.billing_cycle == 'monthly'

    def test_missing_dependency_returns_400_not_500(self, api_client, db):
        company = Company.objects.create(code='acme', name='Acme')
        cat = Module.objects.create(code='catalogue', name='Catálogo')
        pos = Module.objects.create(code='pos', name='POS')
        pos.depends.set([cat])  # pos requires catalogue active
        operator = _user_with_caps('l0_prov2@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(SUBS_URL, {
            'company': company.pk, 'module': pos.pk, 'status': 'active',
        }, format='json')
        assert res.status_code == 400
        assert 'catalogue' in str(res.data)

    def test_read_only_operator_cannot_write(self, api_client, db):
        company = Company.objects.create(code='acme', name='Acme')
        cat = Module.objects.create(code='catalogue', name='Catálogo')
        viewer = _user_with_caps('l0_view@practicayoruba.mx', ['platform.view'])
        api_client.force_login(viewer)
        res = api_client.post(SUBS_URL, {
            'company': company.pk, 'module': cat.pk, 'status': 'active',
        }, format='json')
        assert res.status_code == 403

    def test_operator_can_list_subscriptions(self, api_client, db):
        company = Company.objects.create(code='acme', name='Acme')
        cat = Module.objects.create(code='catalogue', name='Catálogo')
        CompanyModuleSubscription.objects.create(
            company=company, module=cat,
            status=CompanyModuleSubscription.Status.ACTIVE,
        )
        viewer = _user_with_caps('l0_list@practicayoruba.mx', ['platform.view'])
        api_client.force_login(viewer)
        res = api_client.get(SUBS_URL)
        assert res.status_code == 200
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        assert any(r['module_code'] == 'catalogue' for r in rows)

    def test_anonymous_is_unauthorized(self, api_client, db):
        res = api_client.get(SUBS_URL)
        assert res.status_code == 401
