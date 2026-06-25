"""
Tests — Idempotency-Key en checkout (T-603, DEC-BC-03).

Verifica:
  - test_double_post_same_key_creates_one_order: dos POSTs con el mismo
    Idempotency-Key retornan el mismo order_number y solo hay 1 Order.
  - test_double_post_same_key_decrements_stock_once: el stock solo se
    decrementa en el primer POST; el segundo retorna la respuesta cacheada.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch

from apps.catalogue.models import Category, Product
from apps.inventory.services import InventoryService
from apps.orders.models import Order, CheckoutAttempt, ShippingZone

pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v2/orders/'
ITEMS_URL    = '/api/v2/cart/items/'

ADDR = {
    'recipient_name': 'Test Idem',
    'street': 'Av. Hidalgo 50',
    'city': 'CDMX',
    'state': 'CMX',
    'zip_code': '06600',
    'country': 'MX',
}

IDEMPOTENCY_KEY = 'test-idem-key-abc123'


@pytest.fixture
def zone_cdmx(db):
    zone, _ = ShippingZone.objects.get_or_create(
        zip_code_prefix='06', defaults={'name': 'Ciudad de México', 'is_active': True}
    )
    return zone


@pytest.fixture
def cat_idem_co(db):
    return Category.objects.create(name='Cat Idem CO', slug='cat-idem-co', is_active=True)


@pytest.fixture
def prod_idem_co(db, cat_idem_co):
    _p = Product.objects.create(
        name='Prod Idem CO', slug='prod-idem-co', sku='IDEM-CO-001',
        description='',
        price=Decimal('300.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_idem_co)
    return _p


@pytest.fixture
def client_with_item(auth_client, prod_idem_co, zone_cdmx):
    auth_client.post(ITEMS_URL, {'product_id': prod_idem_co.pk, 'quantity': 1}, format='json')
    return auth_client


class TestCheckoutIdempotency:

    def test_double_post_same_key_creates_one_order(
        self, client_with_item, user, prod_idem_co, db
    ):
        """
        T-603: dos POSTs con el mismo Idempotency-Key retornan el mismo
        order_number y solo crean 1 Order en la BD.
        """
        with patch.object(InventoryService, 'check_availability', return_value=[]), \
             patch.object(InventoryService, 'decrement', return_value=None):
            res1 = client_with_item.post(
                CHECKOUT_URL, {'address': ADDR}, format='json',
                HTTP_IDEMPOTENCY_KEY=IDEMPOTENCY_KEY,
            )

        assert res1.status_code == 201, f'Primera peticion fallo: {res1.data}'
        order_number = res1.data['order_number']

        # Segunda peticion con el mismo carrito vaciado ya no importa —
        # el checkout lo responde desde CheckoutAttempt cacheado.
        with patch.object(InventoryService, 'check_availability', return_value=[]), \
             patch.object(InventoryService, 'decrement', return_value=None):
            res2 = client_with_item.post(
                CHECKOUT_URL, {'address': ADDR}, format='json',
                HTTP_IDEMPOTENCY_KEY=IDEMPOTENCY_KEY,
            )

        assert res2.status_code == 201, f'Segunda peticion fallo: {res2.data}'
        assert res2.data['order_number'] == order_number, (
            f'Segunda peticion debio retornar el mismo order_number; '
            f'res1={order_number}, res2={res2.data["order_number"]}'
        )

        order_count = Order.objects.filter(user=user).count()
        assert order_count == 1, (
            f'Solo debe haber 1 Order; hay {order_count}'
        )

        attempt_count = CheckoutAttempt.objects.filter(
            user=user, idempotency_key=IDEMPOTENCY_KEY
        ).count()
        assert attempt_count == 1, (
            f'Solo debe haber 1 CheckoutAttempt; hay {attempt_count}'
        )

    def test_double_post_same_key_decrements_stock_once(
        self, client_with_item, user, prod_idem_co, db
    ):
        """
        T-603b: el stock solo se decrementa en el primer POST;
        el segundo retorna la respuesta cacheada sin tocar stock de nuevo.
        """
        with patch.object(
            InventoryService, 'check_availability', return_value=[]
        ) as mock_check, patch.object(
            InventoryService, 'decrement', return_value=None
        ) as mock_decrement:
            client_with_item.post(
                CHECKOUT_URL, {'address': ADDR}, format='json',
                HTTP_IDEMPOTENCY_KEY=IDEMPOTENCY_KEY + '-stock',
            )

        first_check_calls = mock_check.call_count
        first_decrement_calls = mock_decrement.call_count

        # Segunda peticion — mismo key: respuesta cacheada, no llama a inventory
        with patch.object(
            InventoryService, 'check_availability', return_value=[]
        ) as mock_check2, patch.object(
            InventoryService, 'decrement', return_value=None
        ) as mock_decrement2:
            client_with_item.post(
                CHECKOUT_URL, {'address': ADDR}, format='json',
                HTTP_IDEMPOTENCY_KEY=IDEMPOTENCY_KEY + '-stock',
            )

        assert mock_check2.call_count == 0, (
            'Segunda peticion (cacheada) no debe llamar check_availability'
        )
        assert mock_decrement2.call_count == 0, (
            'Segunda peticion (cacheada) no debe decrementar stock'
        )
