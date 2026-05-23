"""
Tests — Idempotencia de checkout via CheckoutAttempt table (DEC-BC-03)

T-301: test_checkout_idempotency_key_returns_cached_response
T-302: test_checkout_idempotency_key_different_keys_create_separate_orders
T-303: test_checkout_idempotency_key_ignored_for_anonymous
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.orders.models import CheckoutAttempt, Order

pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v1/orders/checkout/'
ITEMS_URL    = '/api/v1/cart/items/'

ADDR = {
    'recipient_name': 'Idm User',
    'street': 'Av. Reforma 1',
    'city': 'CDMX',
    'state': 'Ciudad de Mexico',
    'zip_code': '06600',
    'country': 'MX',
}


@pytest.fixture
def cat_idm_co(db):
    return Category.objects.create(name='Cat Idm CO', slug='cat-idm-co', is_active=True)


@pytest.fixture
def prod_idm_co(db, cat_idm_co):
    return Product.objects.create(
        name='Prod Idm CO', slug='prod-idm-co', sku='IDM-CO-001',
        description='', category=cat_idm_co,
        price=Decimal('400.00'), stock=20,
        is_active=True, is_published=True,
    )


@pytest.fixture
def auth_cart_idm(auth_client, prod_idm_co):
    """auth_client con 1 item en carrito listo para checkout."""
    auth_client.post(ITEMS_URL, {'product_id': prod_idm_co.pk, 'quantity': 1}, format='json')
    return auth_client


class TestCheckoutIdempotency:

    def test_checkout_idempotency_key_returns_cached_response(
        self, auth_cart_idm, prod_idm_co, db
    ):
        """
        T-301: POST con Idempotency-Key → 201 + orden creada.
        Segundo POST con MISMO Idempotency-Key → 201 + MISMO order_number,
        SIN crear nueva orden. 1 CheckoutAttempt en BD.
        """
        headers = {'HTTP_IDEMPOTENCY_KEY': 'IDM-KEY-001'}

        # Primera llamada: crea orden
        res1 = auth_cart_idm.post(CHECKOUT_URL, {'address': ADDR}, format='json', **headers)
        assert res1.status_code == 201
        order_number_1 = res1.data['order_number']

        # Re-añadir item al carrito (el checkout lo vació)
        auth_cart_idm.post(ITEMS_URL, {'product_id': prod_idm_co.pk, 'quantity': 1}, format='json')

        # Segunda llamada con MISMA clave → respuesta cacheada
        res2 = auth_cart_idm.post(CHECKOUT_URL, {'address': ADDR}, format='json', **headers)
        assert res2.status_code == 201
        assert res2.data['order_number'] == order_number_1, (
            'El segundo POST con la misma Idempotency-Key debe retornar la misma orden'
        )

        # Solo 1 orden creada para esta clave
        assert Order.objects.filter(order_number=order_number_1).count() == 1
        assert CheckoutAttempt.objects.filter(idempotency_key='IDM-KEY-001').count() == 1

    def test_checkout_idempotency_key_different_keys_create_separate_orders(
        self, auth_client, prod_idm_co, db
    ):
        """
        T-302: dos Idempotency-Keys distintas → dos órdenes distintas.
        """
        for key in ('KEY-A', 'KEY-B'):
            auth_client.post(ITEMS_URL, {'product_id': prod_idm_co.pk, 'quantity': 1}, format='json')
            res = auth_client.post(
                CHECKOUT_URL, {'address': ADDR}, format='json',
                **{'HTTP_IDEMPOTENCY_KEY': key},
            )
            assert res.status_code == 201

        assert Order.objects.count() == 2
        assert CheckoutAttempt.objects.count() == 2

    def test_checkout_idempotency_key_ignored_for_anonymous(
        self, api_client, prod_idm_co, db
    ):
        """
        T-303: usuario anónimo con Idempotency-Key → checkout se procesa normalmente
        (la clave se ignora porque no hay identidad de usuario estable).
        """
        # Add item without a cart — endpoint creates one and returns its token
        # in the X-Cart-Token response header.
        r_item = api_client.post(
            ITEMS_URL, {'product_id': prod_idm_co.pk, 'quantity': 1},
            format='json',
        )
        assert r_item.status_code == 201
        cart_token = r_item['X-Cart-Token']

        payload = {
            'address': ADDR,
            'cart_token': cart_token,
            'guest_email': 'guest@example.com',
        }
        res = api_client.post(
            CHECKOUT_URL, payload, format='json',
            HTTP_IDEMPOTENCY_KEY='ANON-KEY-001',
        )
        assert res.status_code == 201
        # Ningun CheckoutAttempt creado para usuarios anonimos
        assert CheckoutAttempt.objects.count() == 0
