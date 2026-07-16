"""
Tests — ShippingZone ya NO bloquea el checkout (DEC-BC-18 revertida 2026-07-01)

Antes: CheckoutSerializer.validate_address rechazaba un zip_code no cubierto por
ninguna ShippingZone activa (error ZONE_NOT_COVERED, 400).

Ahora: el costo de envío se deriva del ShippingMethod elegido, no de la zona, y
la dirección es responsabilidad del comprador (el front pide confirmación antes
de pagar). Un C.P. fuera de zona NO debe rechazar el checkout. Estos tests
verifican esa nueva política: ``ZONE_NOT_COVERED`` no aparece, con o sin zonas.
"""
import pytest
from decimal import Decimal
from apps.modules.catalogue.models import Category, Product
from apps.modules.orders.models import ShippingZone

pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v2/orders/'
ITEMS_URL    = '/api/v2/cart/items/'

ADDR_COVERED = {
    'recipient_name': 'Ana Torres',
    'street': 'Av. Insurgentes 200',
    'city': 'CDMX',
    'state': 'Ciudad de México',
    'zip_code': '06600',
    'country': 'MX',
}

ADDR_NOT_COVERED = {
    'recipient_name': 'Bob Smith',
    'street': 'Calle Sin Zona 1',
    'city': 'Villa Remota',
    'state': 'Zona Desconocida',
    'zip_code': '99999',
    'country': 'MX',
}


@pytest.fixture(autouse=True)
def _isolate_zones(db):
    # Las migraciones siembran ShippingZone; estos tests controlan la tabla.
    # Es dentro de la transacción del test -> se revierte al terminar.
    ShippingZone.objects.all().delete()
    yield


@pytest.fixture
def zone(_isolate_zones):
    return ShippingZone.objects.create(
        name='Ciudad de México', zip_code_prefix='06', is_active=True,
    )


@pytest.fixture
def cat_sz(db):
    return Category.objects.create(name='Cat SZ', slug='cat-sz', is_active=True)


@pytest.fixture
def prod_sz(db, cat_sz):
    _p = Product.objects.create(
        name='Prod SZ', slug='prod-sz', sku='SZ-001',
        description='', short_description='',
        price=Decimal('200.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_sz)
    return _p


@pytest.fixture
def cart_with_item(auth_client, prod_sz):
    auth_client.post(ITEMS_URL, {'product_id': prod_sz.pk, 'quantity': 1}, format='json')
    return auth_client


def _no_zone_error(response):
    """El checkout no debe rechazarse por cobertura de zona."""
    return 'ZONE_NOT_COVERED' not in str(response.json())


class TestShippingZoneNoLongerGatesCheckout:

    def test_uncovered_zip_not_blocked_by_zone(self, cart_with_item, zone):
        r = cart_with_item.post(CHECKOUT_URL, {'address': ADDR_NOT_COVERED}, format='json')
        assert _no_zone_error(r)

    def test_covered_zip_not_blocked(self, cart_with_item, zone):
        r = cart_with_item.post(CHECKOUT_URL, {'address': ADDR_COVERED}, format='json')
        assert _no_zone_error(r)

    def test_no_active_zones_does_not_block(self, cart_with_item, db):
        ShippingZone.objects.all().delete()
        r = cart_with_item.post(CHECKOUT_URL, {'address': ADDR_COVERED}, format='json')
        assert _no_zone_error(r)

    def test_inactive_zone_does_not_block(self, cart_with_item, db):
        ShippingZone.objects.create(name='Inactiva', zip_code_prefix='06', is_active=False)
        r = cart_with_item.post(CHECKOUT_URL, {'address': ADDR_NOT_COVERED}, format='json')
        assert _no_zone_error(r)
