"""Tests — ShippingZone validation in CheckoutSerializer (DEC-BC-18)."""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.orders.models import ShippingZone

pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v1/orders/checkout/'
ITEMS_URL    = '/api/v1/cart/items/'

ADDR_COVERED = {
    'recipient_name': 'Ana Torres',
    'street':         'Av. Insurgentes 200',
    'city':           'CDMX',
    'state':          'Ciudad de México',
    'zip_code':       '06600',
    'country':        'MX',
}
ADDR_NOT_COVERED = {
    'recipient_name': 'Bob Smith',
    'street':         'Calle Sin Zona 1',
    'city':           'Villa Remota',
    'state':          'Zona Desconocida',
    'zip_code':       '99999',
    'country':        'MX',
}


@pytest.fixture
def zone(db):
    return ShippingZone.objects.create(
        name='Ciudad de México', zip_code_prefix='06', is_active=True,
    )


@pytest.fixture
def cat_sz(db):
    return Category.objects.create(name='Cat SZ', slug='cat-sz', is_active=True)


@pytest.fixture
def prod_sz(db, cat_sz):
    return Product.objects.create(
        name='Prod SZ', slug='prod-sz', sku='SZ-001',
        description='', category=cat_sz,
        price=Decimal('200.00'), stock=20,
        is_active=True, is_published=True,
    )


@pytest.fixture
def cart_sz(auth_client, prod_sz):
    auth_client.post(ITEMS_URL, {'product_id': prod_sz.pk, 'quantity': 1}, format='json')
    return auth_client


class TestShippingZoneValidation:

    def test_uncovered_zip_returns_400(self, cart_sz, zone):
        r = cart_sz.post(CHECKOUT_URL, {'address': ADDR_NOT_COVERED}, format='json')
        assert r.status_code == 400

    def test_uncovered_zip_error_code(self, cart_sz, zone):
        r = cart_sz.post(CHECKOUT_URL, {'address': ADDR_NOT_COVERED}, format='json')
        assert 'ZONE_NOT_COVERED' in str(r.json())

    def test_covered_zip_passes_zone_check(self, cart_sz, zone):
        r = cart_sz.post(CHECKOUT_URL, {'address': ADDR_COVERED}, format='json')
        assert r.status_code != 400 or 'ZONE_NOT_COVERED' not in str(r.json())

    def test_no_active_zones_rejects_all(self, cart_sz, db):
        ShippingZone.objects.all().delete()
        r = cart_sz.post(CHECKOUT_URL, {'address': ADDR_COVERED}, format='json')
        assert r.status_code == 400
        assert 'ZONE_NOT_COVERED' in str(r.json())

    def test_inactive_zone_not_counted(self, cart_sz, db):
        ShippingZone.objects.all().delete()
        ShippingZone.objects.create(
            name='Inactiva', zip_code_prefix='06', is_active=False,
        )
        r = cart_sz.post(CHECKOUT_URL, {'address': ADDR_COVERED}, format='json')
        assert r.status_code == 400
        assert 'ZONE_NOT_COVERED' in str(r.json())
