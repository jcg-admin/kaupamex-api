"""Tests — ``GET /api/v2/web/vcard/download/`` (tarea #397).

Contrato adaptado de ``odoo19c: addons/web/controllers/vcard.py``
(``odoo-tools@622ddc2a``). El primitivo real —``ResPartner._get_vcard_file()``—
ya tiene su propia cobertura de contenido (formato RFC 6350); aquí se
verifica la frontera HTTP: capacidad, un contacto vs varios, e ids
inexistentes.
"""
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model

import pytest

from addons.authz.models import Capability, Module, Role, RoleAssignment
from addons.base.models.res_partner import ResPartner

pytestmark = pytest.mark.django_db

VCARD_URL = '/api/v2/web/vcard/download/'


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


class TestVcardDownloadGate:
    """El candado ``web.vcard.download`` gobierna el endpoint."""

    def test_anonymous_is_unauthorized(self, api_client, user):
        res = api_client.get(VCARD_URL, {'partner_ids': str(user.partner.pk)})
        assert res.status_code == 401

    def test_user_without_capability_is_denied(self, api_client, db, user):
        outsider = get_user_model().objects.create_user(
            login='vcard_outsider@practicayoruba.mx', password='TestPass123!')
        api_client.force_login(outsider)
        res = api_client.get(VCARD_URL, {'partner_ids': str(user.partner.pk)})
        assert res.status_code == 403


class TestVcardDownloadResult:
    """Camino positivo — con la capacidad concedida."""

    def test_single_partner_returns_vcf(self, api_client, db, user):
        operator = _user_with_capability(
            'vcard_operator@practicayoruba.mx', 'web.vcard.download')
        api_client.force_login(operator)
        res = api_client.get(VCARD_URL, {'partner_ids': str(user.partner.pk)})
        assert res.status_code == 200
        assert res['Content-Type'] == 'text/vcard'
        body = res.content.decode()
        assert body.startswith('BEGIN:VCARD')
        assert body.rstrip().endswith('END:VCARD')
        assert f'FN:{user.partner.name}' in body

    def test_multiple_partners_return_zip(self, api_client, db, user):
        second = ResPartner.objects.create(name='Segundo Contacto')
        operator = _user_with_capability(
            'vcard_operator2@practicayoruba.mx', 'web.vcard.download')
        api_client.force_login(operator)
        res = api_client.get(
            VCARD_URL,
            {'partner_ids': f'{user.partner.pk},{second.pk}'})
        assert res.status_code == 200
        assert res['Content-Type'] == 'application/zip'
        with zipfile.ZipFile(BytesIO(res.content)) as archive:
            assert len(archive.namelist()) == 2

    def test_missing_partner_ids_returns_400(self, api_client, db):
        operator = _user_with_capability(
            'vcard_operator3@practicayoruba.mx', 'web.vcard.download')
        api_client.force_login(operator)
        res = api_client.get(VCARD_URL)
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'PARTNER_IDS_REQUIRED'

    def test_unknown_partner_id_returns_404(self, api_client, db):
        operator = _user_with_capability(
            'vcard_operator4@practicayoruba.mx', 'web.vcard.download')
        api_client.force_login(operator)
        res = api_client.get(VCARD_URL, {'partner_ids': '999999999'})
        assert res.status_code == 404
        assert res.data['codigo_error'] == 'PARTNER_NOT_FOUND'
