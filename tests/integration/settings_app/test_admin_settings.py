"""
Tests de integracion — Admin SiteSettings (UC-ADM-04)
T-119: SiteSettingsView — GET/PATCH /api/v1/admin/settings/
"""
import pytest
from apps.settings_app.models import SiteSettings

pytestmark = pytest.mark.integration

SETTINGS_URL = '/api/v1/admin/settings/'


@pytest.fixture
def site_settings(db):
    return SiteSettings.get_or_create_defaults()


class TestAdminSiteSettings:

    def test_admin_puede_ver_settings(self, admin_auth_client, site_settings, db):
        r = admin_auth_client.get(SETTINGS_URL)
        assert r.status_code == 200

    def test_comprador_no_puede_ver_settings(self, auth_client, site_settings, db):
        r = auth_client.get(SETTINGS_URL)
        assert r.status_code == 403

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.get(SETTINGS_URL)
        assert r.status_code == 401

    def test_campos_retornados(self, admin_auth_client, site_settings, db):
        r = admin_auth_client.get(SETTINGS_URL)
        data = r.json()
        for field in ['site_name', 'iva_rate', 'currency', 'max_return_days']:
            assert field in data

    def test_admin_puede_actualizar_settings(self, admin_auth_client, site_settings, db):
        r = admin_auth_client.patch(
            SETTINGS_URL,
            {'max_return_days': 45},
            format='json',
        )
        assert r.status_code == 200
        assert r.json()['max_return_days'] == 45

    def test_comprador_no_puede_actualizar_settings(self, auth_client, site_settings, db):
        r = auth_client.patch(
            SETTINGS_URL,
            {'max_return_days': 99},
            format='json',
        )
        assert r.status_code == 403
