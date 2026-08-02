"""Catálogo L0 de módulos — ``GET /api/v2/platform/modules/`` (#179).

Endpoint read-only que la consola del operador consume para pintar los módulos
contratables con su metadata de catálogo (``is_application``/``tier``/
``category``/``depends``). Gateado con ``platform.view`` (data-driven vía
``HasCapability``, NO ``is_staff``).
"""
from django.contrib.auth import get_user_model

import pytest

from addons.authz.models import Capability, Module, Role, RoleAssignment

pytestmark = pytest.mark.integration

MODULES_URL = '/api/v2/platform/modules/'


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


class TestPlatformModulesCatalog:
    def test_operator_lists_catalog_with_metadata(self, api_client, db):
        catalogue = Module.objects.create(
            code='catalogue', name='Catálogo', is_application=True,
            tier=Module.Tier.FREE, category='Order Management', version='1.0.0',
        )
        inventory = Module.objects.create(code='inventory', name='Inventario', is_application=True)
        inventory.depends.set([catalogue])
        operator = _user_with_caps('l0_modules@practicayoruba.mx', ['platform.view'])
        api_client.force_login(operator)

        res = api_client.get(MODULES_URL)
        assert res.status_code == 200
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        by_code = {r['code']: r for r in rows}
        assert by_code['catalogue']['is_application'] is True
        assert by_code['catalogue']['tier'] == 'free'
        assert by_code['catalogue']['category'] == 'Order Management'
        # depends expone los códigos, no los ids.
        assert by_code['inventory']['depends'] == ['catalogue']

    def test_catalog_is_read_only(self, api_client, db):
        operator = _user_with_caps('l0_ro@practicayoruba.mx', ['platform.view'])
        api_client.force_login(operator)
        res = api_client.post(MODULES_URL, {'code': 'x', 'name': 'X'}, format='json')
        assert res.status_code == 405

    def test_without_platform_view_denied(self, api_client, db):
        nobody = _user_with_caps('l0_none@practicayoruba.mx', ['account.view'])
        api_client.force_login(nobody)
        res = api_client.get(MODULES_URL)
        assert res.status_code == 403
