"""
Tests de integracion — Public SiteSettings (US-1.1, closes ERR-14)

GET /api/v1/config/public-settings/ — public read-only storefront subset.
No auth required; exposes ONLY the storefront-safe fields and NEVER any
admin/secret field.
"""
import pytest
from apps.settings_app.models import SiteSettings

pytestmark = pytest.mark.integration

PUBLIC_SETTINGS_URL = '/api/v1/config/public-settings/'

# Exact storefront-safe allowlist returned by the public endpoint.
ALLOWED_FIELDS = {
    'iva_rate',
    'free_shipping_threshold',
    'payment_timeout_minutes',
    'min_stock_threshold',
}

# Admin-only / sensitive fields that MUST NOT leak through the public endpoint.
FORBIDDEN_FIELDS = {
    'support_email',
    'phone',
    'address',
    'social_links',
    'site_name',
    'currency',
    'order_timeout_minutes',
    'max_return_days',
    'referral_active',
    'referral_welcome_discount',
    'referral_reward_discount',
    'logo',
}


@pytest.fixture
def site_settings(db):
    return SiteSettings.get_or_create_defaults()


class TestPublicSiteSettings:

    def test_unauthenticated_returns_200(self, api_client, site_settings, db):
        r = api_client.get(PUBLIC_SETTINGS_URL)
        assert r.status_code == 200

    def test_exact_subset_present(self, api_client, site_settings, db):
        r = api_client.get(PUBLIC_SETTINGS_URL)
        data = r.json()
        for field in ALLOWED_FIELDS:
            assert field in data, f'expected storefront field missing: {field}'

    def test_admin_and_secret_fields_absent(self, api_client, site_settings, db):
        r = api_client.get(PUBLIC_SETTINGS_URL)
        data = r.json()
        leaked = FORBIDDEN_FIELDS & set(data.keys())
        assert not leaked, f'public endpoint leaked admin/secret fields: {leaked}'

    def test_response_keys_are_exactly_the_allowlist(self, api_client, site_settings, db):
        r = api_client.get(PUBLIC_SETTINGS_URL)
        data = r.json()
        assert set(data.keys()) == ALLOWED_FIELDS, (
            f'public endpoint keys {set(data.keys())} != allowlist {ALLOWED_FIELDS}'
        )

    def test_no_write_methods(self, api_client, site_settings, db):
        # Public config is read-only: writes must be rejected.
        assert api_client.post(PUBLIC_SETTINGS_URL, {}, format='json').status_code in (403, 405)
        assert api_client.patch(PUBLIC_SETTINGS_URL, {}, format='json').status_code in (403, 405)
        assert api_client.put(PUBLIC_SETTINGS_URL, {}, format='json').status_code in (403, 405)
