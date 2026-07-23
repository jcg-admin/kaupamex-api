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

from addons.authz.models import Capability, Module, Role, RoleAssignment
from addons.company.models import Company

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


class TestPlatformCompaniesLifecycle:
    """Alta + suspensión/reactivación del tenant (UC-PLT-12), escritura L0
    gobernada por ``platform.provision``."""

    def test_operator_can_create_tenant_as_trial(self, api_client, db):
        operator = _user_with_caps('l0_create@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(COMPANIES_URL, {
            'code': 'zapateria-dos', 'name': 'Zapatería DOS',
            'billing_email': 'facturacion@zapateriados.mx',
        }, format='json')
        assert res.status_code == 201, res.data
        company = Company.objects.get(code='zapateria-dos')
        # El estado inicial es SIEMPRE trial (fijo en alta, no editable).
        assert company.status == Company.Status.TRIAL

    def test_create_forces_trial_even_if_status_sent(self, api_client, db):
        operator = _user_with_caps('l0_create2@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(COMPANIES_URL, {
            'code': 'tienda-x', 'name': 'Tienda X', 'status': 'active',
        }, format='json')
        assert res.status_code == 201, res.data
        assert Company.objects.get(code='tienda-x').status == Company.Status.TRIAL

    def test_read_only_operator_cannot_create(self, api_client, db):
        viewer = _user_with_caps('l0_ro_create@practicayoruba.mx', ['platform.view'])
        api_client.force_login(viewer)
        res = api_client.post(COMPANIES_URL, {'code': 'nope', 'name': 'Nope'}, format='json')
        assert res.status_code == 403

    def test_operator_can_suspend_and_reactivate(self, api_client, db):
        company = Company.objects.create(
            code='acme', name='Acme', status=Company.Status.ACTIVE,
        )
        operator = _user_with_caps('l0_susp@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(f'{COMPANIES_URL}{company.pk}/suspend/')
        assert res.status_code == 200, res.data
        company.refresh_from_db()
        assert company.status == Company.Status.SUSPENDED
        res = api_client.post(f'{COMPANIES_URL}{company.pk}/reactivate/')
        assert res.status_code == 200, res.data
        company.refresh_from_db()
        assert company.status == Company.Status.ACTIVE

    def test_cannot_suspend_system_company(self, api_client, db):
        system = Company.objects.create(
            code='kaupamex_global', name='Kaupamex', is_system=True,
            status=Company.Status.ACTIVE,
        )
        operator = _user_with_caps('l0_sys@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(f'{COMPANIES_URL}{system.pk}/suspend/')
        assert res.status_code == 400
        system.refresh_from_db()
        assert system.status == Company.Status.ACTIVE

    def test_reactivate_requires_suspended_state(self, api_client, db):
        company = Company.objects.create(
            code='acme2', name='Acme2', status=Company.Status.ACTIVE,
        )
        operator = _user_with_caps('l0_react@practicayoruba.mx', ['platform.provision'])
        api_client.force_login(operator)
        res = api_client.post(f'{COMPANIES_URL}{company.pk}/reactivate/')
        assert res.status_code == 400

    def test_read_only_operator_cannot_suspend(self, api_client, db):
        company = Company.objects.create(
            code='acme3', name='Acme3', status=Company.Status.ACTIVE,
        )
        viewer = _user_with_caps('l0_ro_susp@practicayoruba.mx', ['platform.view'])
        api_client.force_login(viewer)
        res = api_client.post(f'{COMPANIES_URL}{company.pk}/suspend/')
        assert res.status_code == 403
