"""Tests — order_created signal (DEC-BC-19)."""
import pytest
from decimal import Decimal
from apps.addons.catalogue.models import Category, Product
from apps.addons.orders.models import ShippingZone
from apps.addons.settings_app.models import ShippingMethod
from apps.addons.orders.signals import order_created

pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v2/orders/'
ITEMS_URL    = '/api/v2/cart/items/'

ADDR = {
    'recipient_name': 'Signal Test',
    'street':         'Av. Test 100',
    'city':           'CDMX',
    'state':          'CDMX',
    'zip_code':       '06600',
    'country':        'MX',
}


@pytest.fixture
def cat_sig(db):
    return Category.objects.create(name='Cat Sig', slug='cat-sig', is_active=True)


@pytest.fixture
def prod_sig(db, cat_sig):
    _p = Product.objects.create(
        name='Prod Sig', slug='prod-sig', sku='SIG-001',
        description='',
        price=Decimal('100.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_sig)
    return _p


@pytest.fixture
def zone_sig(db):
    zone, _ = ShippingZone.objects.get_or_create(
        zip_code_prefix='06', defaults={'name': 'Ciudad de México', 'is_active': True},
    )
    return zone


@pytest.fixture
def cart_sig(auth_client, prod_sig, zone_sig):
    auth_client.post(ITEMS_URL, {'product_id': prod_sig.pk, 'quantity': 1}, format='json')
    return auth_client


@pytest.fixture
def ship_sig(db):
    """DEC-BC-25: el checkout exige un método de envío activo."""
    return ShippingMethod.objects.create(
        name='Estándar', cost=Decimal('0.00'), estimated_days=5, is_active=True)


class TestOrderCreatedSignal:

    def test_signal_fires_on_checkout(self, cart_sig, ship_sig, db):
        calls = []
        def capture(**kwargs):
            calls.append(kwargs)
        order_created.connect(capture)
        try:
            r = cart_sig.post(
                CHECKOUT_URL,
                {'address': ADDR, 'shipping_method_id': ship_sig.pk},
                format='json')
            assert r.status_code == 201
            assert len(calls) == 1
        finally:
            order_created.disconnect(capture)

    def test_signal_carries_order(self, cart_sig, ship_sig, db):
        received = {}
        def capture(**kwargs):
            received.update(kwargs)
        order_created.connect(capture)
        try:
            cart_sig.post(
                CHECKOUT_URL,
                {'address': ADDR, 'shipping_method_id': ship_sig.pk},
                format='json')
            assert 'order' in received
            assert received['order'].order_number.startswith('PY-')
        finally:
            order_created.disconnect(capture)

    def test_signal_fires_exactly_once(self, cart_sig, ship_sig, db):
        calls = []
        def capture(**kwargs):
            calls.append(kwargs)
        order_created.connect(capture)
        try:
            r = cart_sig.post(
                CHECKOUT_URL,
                {'address': ADDR, 'shipping_method_id': ship_sig.pk},
                format='json')
            assert r.status_code == 201
            assert len(calls) == 1
        finally:
            order_created.disconnect(capture)
