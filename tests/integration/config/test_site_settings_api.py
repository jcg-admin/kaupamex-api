"""
Tests de integración API — SiteSettings (UC-CFG-03)

Campos actuales en el modelo (tras migración 0008_sync_model_drift):
  iva_rate, payment_timeout_minutes, min_stock_threshold,
  free_shipping_threshold, support_email, phone, address, social_links

Campos eliminados (refactorización Sprint 8→18):
  currency, order_timeout_minutes, site_name, avatar_max_size_mb,
  max_addresses_per_user, max_return_days

Contrato:
  GET  /api/v2/config/settings/   — devuelve la configuración actual (admin)
  PATCH /api/v2/config/settings/  — actualiza campos (admin only)
"""
import pytest
from decimal import Decimal
from addons.base.models import SiteSettings

pytestmark = pytest.mark.api


class TestSiteSettingsEndpointGet:
    """GET /api/v2/config/settings/ — solo admin."""

    def test_admin_can_get_settings(self, admin_client):
        res = admin_client.get('/api/v2/config/settings/')
        assert res.status_code == 200
        data = res.json()
        assert 'iva_rate' in data
        # payment_timeout_minutes reemplazó a order_timeout_minutes
        assert 'payment_timeout_minutes' in data

    def test_respuesta_no_incluye_campos_eliminados(self, admin_client):
        """currency, site_name, order_timeout_minutes fueron eliminados."""
        res = admin_client.get('/api/v2/config/settings/')
        data = res.json()
        assert 'currency' not in data
        assert 'site_name' not in data
        assert 'order_timeout_minutes' not in data

    def test_unauthenticated_gets_401(self, api_client):
        res = api_client.get('/api/v2/config/settings/')
        assert res.status_code in (401, 403)

    def test_regular_user_gets_403(self, auth_client):
        res = auth_client.get('/api/v2/config/settings/')
        assert res.status_code == 403


class TestSiteSettingsEndpointPatch:
    """PATCH /api/v2/config/settings/ — solo admin."""

    def test_admin_can_update_iva_rate(self, admin_client):
        res = admin_client.patch(
            '/api/v2/config/settings/',
            {'iva_rate': '0.08'},
            format='json',
        )
        assert res.status_code == 200
        assert Decimal(res.json()['iva_rate']) == Decimal('0.08')

    def test_admin_can_update_payment_timeout(self, admin_client):
        """payment_timeout_minutes reemplaza a order_timeout_minutes."""
        res = admin_client.patch(
            '/api/v2/config/settings/',
            {'payment_timeout_minutes': 45},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['payment_timeout_minutes'] == 45

    def test_regular_user_cannot_patch(self, auth_client):
        res = auth_client.patch(
            '/api/v2/config/settings/',
            {'iva_rate': '0.00'},
            format='json',
        )
        assert res.status_code == 403

    def test_update_persists_to_database(self, admin_client, db):
        admin_client.patch(
            '/api/v2/config/settings/',
            {'payment_timeout_minutes': 60},
            format='json',
        )
        s = SiteSettings.get_current()
        assert s.payment_timeout_minutes == 60

    def test_invalid_iva_rate_returns_400(self, admin_client):
        """Negative test: iva_rate out of valid bounds should return 400."""
        res = admin_client.patch(
            '/api/v2/config/settings/',
            {'iva_rate': '1.5'},  # > 1.0 is invalid
            format='json',
        )
        assert res.status_code == 400

    def test_negative_payment_timeout_returns_400(self, admin_client):
        """Negative test: negative payment_timeout_minutes should return 400."""
        res = admin_client.patch(
            '/api/v2/config/settings/',
            {'payment_timeout_minutes': -10},
            format='json',
        )
        assert res.status_code == 400
