"""
Tests de integración API — SiteSettings (UC-CFG-03)
TDD: RED — endpoint no existe todavía.

Contrato:
  GET  /api/v1/config/settings/   — devuelve la configuración actual (admin)
  PATCH /api/v1/config/settings/  — actualiza campos (admin only)
"""
import pytest
from decimal import Decimal

pytestmark = pytest.mark.api


class TestSiteSettingsEndpointGet:
    """GET /api/v1/config/settings/ — solo admin."""

    def test_admin_can_get_settings(self, admin_client):
        res = admin_client.get('/api/v1/config/settings/')
        assert res.status_code == 200
        data = res.json()
        assert 'iva_rate' in data
        assert 'currency' in data
        assert 'order_timeout_minutes' in data

    def test_unauthenticated_gets_401(self, api_client):
        res = api_client.get('/api/v1/config/settings/')
        assert res.status_code in (401, 403)

    def test_regular_user_gets_403(self, auth_client):
        res = auth_client.get('/api/v1/config/settings/')
        assert res.status_code == 403


class TestSiteSettingsEndpointPatch:
    """PATCH /api/v1/config/settings/ — solo admin."""

    def test_admin_can_update_iva_rate(self, admin_client):
        res = admin_client.patch(
            '/api/v1/config/settings/',
            {'iva_rate': '0.08'},
            format='json',
        )
        assert res.status_code == 200
        assert Decimal(res.json()['iva_rate']) == Decimal('0.08')

    def test_admin_can_update_currency(self, admin_client):
        res = admin_client.patch(
            '/api/v1/config/settings/',
            {'currency': 'USD'},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['currency'] == 'USD'

    def test_invalid_iva_rate_returns_400(self, admin_client):
        res = admin_client.patch(
            '/api/v1/config/settings/',
            {'iva_rate': '2.00'},
            format='json',
        )
        assert res.status_code == 400
        assert 'iva_rate' in res.json()

    def test_invalid_currency_returns_400(self, admin_client):
        res = admin_client.patch(
            '/api/v1/config/settings/',
            {'currency': 'TOOLONG'},
            format='json',
        )
        assert res.status_code == 400

    def test_regular_user_cannot_patch(self, auth_client):
        res = auth_client.patch(
            '/api/v1/config/settings/',
            {'iva_rate': '0.00'},
            format='json',
        )
        assert res.status_code == 403

    def test_update_persists_to_database(self, admin_client, db):
        from apps.settings_app.models import SiteSettings
        admin_client.patch(
            '/api/v1/config/settings/',
            {'order_timeout_minutes': 60},
            format='json',
        )
        s = SiteSettings.get_current()
        assert s.order_timeout_minutes == 60
