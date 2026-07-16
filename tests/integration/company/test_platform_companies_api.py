"""Tests — L0 platform company directory API (UC-PLT-12).

``GET /api/v2/platform/companies/`` es la consola del operador Kaupamex (L0),
cross-company, gobernada por la capacidad de **lectura** ``platform.view`` vía
``HasCapability`` (data-driven; NO ``is_staff``). El scope de lectura es
distinto del de escritura (``platform.provision`` crea/suspende) — least
privilege, sin ventana de seguridad read→write. Cubre:

- operador con ``platform.view`` → 200 en list + retrieve, ve todos los
  companies (cross-company, sin filtro por company);
- usuario autenticado sin la capacidad de lectura → 403 (fail-closed);
- anónimo → 401.

El usuario de prueba NO es superadmin, así que ``HasCapability`` se evalúa de
verdad (sin bypass del resolver).
"""
from django.contrib.auth import get_user_model

from apps.authz.models import Capability, Module, Role, RoleAssignment
from apps.company.models import Company

import pytest

pytestmark = pytest.mark.integration

COMPANIES_URL = '/api/v2/platform/companies/'


def _user_with_caps(email, codes):
    """Usuario NO-superadmin con exactamente las capacidades ``codes`` vía un
    rol dedicado. Como no es superadmin, ``HasCapability`` se evalúa de verdad
    (sin bypass del resolver de superadmin)."""
    caps = []
    for code in codes:
        domain = code.split('.', 1)[0]
        module, _ = Module.objects.get_or_create(
            code=domain, defaults={'name': domain},
        )
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


class TestPlatformCompaniesGate:
    """El candado ``platform.provision`` gobierna el directorio L0 de companies."""

    def test_operator_can_list_all_companies(self, api_client, db):
        # Camino POSITIVO: operador L0 ve todos los companies (cross-company).
        Company.objects.create(code='acme', name='Acme')
        Company.objects.create(code='globex', name='Globex')
        operator = _user_with_caps(
            'l0_operator@practicayoruba.mx', ['platform.view'],
        )
        api_client.force_login(operator)
        res = api_client.get(COMPANIES_URL)
        assert res.status_code == 200
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        codes = {row['code'] for row in rows}
        assert {'acme', 'globex'} <= codes

    def test_operator_can_retrieve_company_detail(self, api_client, db):
        t = Company.objects.create(code='acme', name='Acme')
        operator = _user_with_caps(
            'l0_detail@practicayoruba.mx', ['platform.view'],
        )
        api_client.force_login(operator)
        res = api_client.get(f'{COMPANIES_URL}{t.pk}/')
        assert res.status_code == 200
        assert res.data['code'] == 'acme'
        assert res.data['status'] == Company.Status.TRIAL
        assert res.data['active_modules'] == []
        assert res.data['user_count'] == 0

    def test_user_without_platform_view_is_denied(self, api_client, db):
        # Camino NEGATIVO: autenticado sin la capacidad de lectura → 403.
        Company.objects.create(code='acme', name='Acme')
        outsider = _user_with_caps(
            'l0_outsider@practicayoruba.mx', ['reports.view'],
        )
        api_client.force_login(outsider)
        res = api_client.get(COMPANIES_URL)
        assert res.status_code == 403

    def test_anonymous_is_unauthorized(self, api_client, db):
        # Sin autenticación → 401.
        res = api_client.get(COMPANIES_URL)
        assert res.status_code == 401
