"""Tests — ``GET /api/v2/web/pivot/export_xlsx/`` (tarea #397).

Contrato adaptado de ``odoo19c: addons/web/controllers/pivot.py``
(``odoo-tools@622ddc2a``). No hay modelo que consultar (ver el docstring del
módulo): el JSON ya trae los datos calculados por el cliente, así que el
contrato es puramente de formato — volcar ``data`` a un ``.xlsx`` válido.
"""
import json

from django.contrib.auth import get_user_model

import pytest

from addons.authz.models import Capability, Module, Role, RoleAssignment

pytestmark = pytest.mark.django_db

EXPORT_URL = '/api/v2/web/pivot/export_xlsx/'

_JDATA = {
    'title': 'Ventas',
    'model': 'sale.order',
    'measure_count': 1,
    'col_group_headers': [],
    'measure_headers': [{'title': 'Total', 'is_bold': True}],
    'rows': [
        {'title': 'Total', 'indent': 0,
         'values': [{'value': 100, 'is_bold': True}]},
    ],
}


def _user_with_capability(email, code):
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


class TestPivotExportGate:
    """El candado ``web.pivot.export`` gobierna el endpoint."""

    def test_anonymous_is_unauthorized(self, api_client):
        res = api_client.get(EXPORT_URL, {'data': json.dumps(_JDATA)})
        assert res.status_code == 401

    def test_user_without_capability_is_denied(self, api_client, db):
        outsider = get_user_model().objects.create_user(
            login='pivot_outsider@practicayoruba.mx', password='TestPass123!')
        api_client.force_login(outsider)
        res = api_client.get(EXPORT_URL, {'data': json.dumps(_JDATA)})
        assert res.status_code == 403


class TestPivotExportResult:
    """Camino positivo — con la capacidad concedida."""

    def test_returns_a_valid_xlsx(self, api_client, db):
        operator = _user_with_capability(
            'pivot_exporter@practicayoruba.mx', 'web.pivot.export')
        api_client.force_login(operator)
        res = api_client.get(EXPORT_URL, {'data': json.dumps(_JDATA)})
        assert res.status_code == 200
        assert res['Content-Type'] == (
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet')
        # Un .xlsx es un .zip — su firma son los dos primeros bytes "PK".
        assert res.content[:2] == b'PK'
        assert 'attachment' in res['Content-Disposition']

    def test_missing_data_returns_400(self, api_client, db):
        operator = _user_with_capability(
            'pivot_exporter2@practicayoruba.mx', 'web.pivot.export')
        api_client.force_login(operator)
        res = api_client.get(EXPORT_URL)
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'DATA_REQUIRED'

    def test_invalid_json_returns_400(self, api_client, db):
        operator = _user_with_capability(
            'pivot_exporter3@practicayoruba.mx', 'web.pivot.export')
        api_client.force_login(operator)
        res = api_client.get(EXPORT_URL, {'data': '{not json'})
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'INVALID_JSON'

    def test_empty_data_returns_400(self, api_client, db):
        operator = _user_with_capability(
            'pivot_exporter4@practicayoruba.mx', 'web.pivot.export')
        api_client.force_login(operator)
        res = api_client.get(EXPORT_URL, {'data': json.dumps({})})
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'DATA_REQUIRED'
