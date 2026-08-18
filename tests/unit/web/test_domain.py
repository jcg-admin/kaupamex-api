"""Tests — ``POST /api/v2/web/domain/validate/`` (tarea #397).

Contrato adaptado de ``odoo19c: addons/web/controllers/domain.py``
(``odoo-tools@622ddc2a``). Lo que se verifica es la frontera: quién puede
validar un dominio, qué responde para un dominio bien/mal formado, y qué
responde para un modelo desconocido. La capacidad ``web.domain.validate`` es
deliberadamente amplia (ver el docstring del módulo) — el usuario de prueba
NO es superadmin, así que ``HasCapability`` se evalúa de verdad.
"""
from django.contrib.auth import get_user_model

import pytest

from addons.authz.models import Capability, Module, Role, RoleAssignment

pytestmark = pytest.mark.django_db

VALIDATE_URL = '/api/v2/web/domain/validate/'


def _user_with_capability(email, code):
    """Usuario NO-superadmin con exactamente ``code`` vía un rol dedicado."""
    domain = code.split('.', 1)[0]
    module, _ = Module.objects.get_or_create(code=domain, defaults={'name': domain})
    cap, _ = Capability.objects.get_or_create(
        code=code, defaults={'module': module, 'name': code})
    role, _ = Role.objects.get_or_create(
        code=f'role_{code.replace(".", "_")}', defaults={'name': code})
    role.capabilities.set([cap])
    u = get_user_model().objects.create_user(
        login=email, password='TestPass123!')
    RoleAssignment.objects.create(user=u, role=role)
    return u


class TestDomainValidateGate:
    """El candado ``web.domain.validate`` gobierna el endpoint."""

    def test_anonymous_is_unauthorized(self, api_client):
        res = api_client.post(
            VALIDATE_URL,
            {'model': 'base.ResPartner', 'domain': [['name', '=', 'x']]},
            format='json')
        assert res.status_code == 401

    def test_user_without_capability_is_denied(self, api_client, db):
        outsider = get_user_model().objects.create_user(
            login='outsider@practicayoruba.mx', password='TestPass123!')
        api_client.force_login(outsider)
        res = api_client.post(
            VALIDATE_URL,
            {'model': 'base.ResPartner', 'domain': [['name', '=', 'x']]},
            format='json')
        assert res.status_code == 403


class TestDomainValidateResult:
    """Camino positivo — con la capacidad concedida."""

    def test_valid_domain_returns_true(self, api_client, db):
        operator = _user_with_capability(
            'validator@practicayoruba.mx', 'web.domain.validate')
        api_client.force_login(operator)
        res = api_client.post(
            VALIDATE_URL,
            {'model': 'base.ResPartner', 'domain': [['name', '=', 'x']]},
            format='json')
        assert res.status_code == 200
        assert res.data['valid'] is True

    def test_empty_domain_is_valid(self, api_client, db):
        """Un dominio vacío es el dominio TRUE — siempre válido."""
        operator = _user_with_capability(
            'validator2@practicayoruba.mx', 'web.domain.validate')
        api_client.force_login(operator)
        res = api_client.post(
            VALIDATE_URL, {'model': 'base.ResPartner', 'domain': []},
            format='json')
        assert res.status_code == 200
        assert res.data['valid'] is True

    def test_unknown_operator_returns_false(self, api_client, db):
        """Un operador fuera de ``CONDITION_OPERATORS`` no compila —
        ``valid: False``, no un 500 — mismo contrato que la referencia
        (``except Exception: return False``)."""
        operator = _user_with_capability(
            'validator3@practicayoruba.mx', 'web.domain.validate')
        api_client.force_login(operator)
        res = api_client.post(
            VALIDATE_URL,
            {'model': 'base.ResPartner',
             'domain': [['name', 'not_a_real_operator', 'x']]},
            format='json')
        assert res.status_code == 200
        assert res.data['valid'] is False

    def test_unknown_field_returns_false(self, api_client, db):
        operator = _user_with_capability(
            'validator4@practicayoruba.mx', 'web.domain.validate')
        api_client.force_login(operator)
        res = api_client.post(
            VALIDATE_URL,
            {'model': 'base.ResPartner',
             'domain': [['no_such_field_at_all', '=', 'x']]},
            format='json')
        assert res.status_code == 200
        assert res.data['valid'] is False

    def test_unknown_model_returns_400(self, api_client, db):
        operator = _user_with_capability(
            'validator5@practicayoruba.mx', 'web.domain.validate')
        api_client.force_login(operator)
        res = api_client.post(
            VALIDATE_URL,
            {'model': 'base.NoSuchModelEver', 'domain': []},
            format='json')
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'INVALID_MODEL'
