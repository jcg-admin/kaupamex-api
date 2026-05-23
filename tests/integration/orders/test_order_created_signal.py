"""Tests — order_created signal (DEC-BC-19)."""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.orders.signals import order_created

pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v1/orders/checkout/'
ITEMS_URL    = '/api/v1/cart/items/'

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
    return Product.objects.create(
        name='Prod Sig', slug='prod-sig', sku='SIG-001',
        description='', category=cat_sig,
        price=Decimal('100.00'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def cart_sig(auth_client, prod_sig):
    auth_client.post(ITEMS_URL, {'product_id': prod_sig.pk, 'quantity': 1}, format='json')
    return auth_client


class TestOrderCreatedSignal:

    def test_signal_fires_on_checkout(self, cart_sig, db):
        calls = []
        def capture(**kwargs):
            calls.append(kwargs)
        order_created.connect(capture)
        try:
            r = cart_sig.post(CHECKOUT_URL, {'address': ADDR}, format='json')
            assert r.status_code == 201
            assert len(calls) == 1
        finally:
            order_created.disconnect(capture)

    def test_signal_carries_order(self, cart_sig, db):
        received = {}
        def capture(**kwargs):
            received.update(kwargs)
        order_created.connect(capture)
        try:
            cart_sig.post(CHECKOUT_URL, {'address': ADDR}, format='json')
            assert 'order' in received
            assert received['order'].order_number.startswith('PY-')
        finally:
            order_created.disconnect(capture)

    def test_signal_fires_exactly_once(self, cart_sig, db):
        calls = []
        def capture(**kwargs):
            calls.append(kwargs)
        order_created.connect(capture)
        try:
            r = cart_sig.post(CHECKOUT_URL, {'address': ADDR}, format='json')
            assert r.status_code == 201
            assert len(calls) == 1
        finally:
            order_created.disconnect(capture)
