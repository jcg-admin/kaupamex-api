"""
Tests — VoucherUsage single-use-by-user enforcement

T-302 / DEC-BC-10:
  test_voucher_used_twice_same_user_rejects_409
  test_current_uses_increments_atomic
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.catalogue.models import Category, Product
from apps.voucher.models import Voucher, VoucherUsage

pytestmark = pytest.mark.integration

CHECKOUT_URL     = '/api/v1/orders/checkout/'
ITEMS_URL        = '/api/v1/cart/items/'
CART_VOUCHER_URL = '/api/v1/cart/voucher/'

ADDR = {
    'recipient_name': 'VchUsage User',
    'street': 'Av. Insurgentes 1',
    'city': 'CDMX',
    'state': 'Ciudad de Mexico',
    'zip_code': '06600',
    'country': 'MX',
}


@pytest.fixture
def cat_vu(db):
    return Category.objects.create(name='Cat VU', slug='cat-vu', is_active=True)


@pytest.fixture
def prod_vu(db, cat_vu):
    return Product.objects.create(
        name='Prod VU', slug='prod-vu', sku='VU-001',
        description='', category=cat_vu,
        price=Decimal('500.00'), stock=30,
        is_active=True, is_published=True,
    )


@pytest.fixture
def voucher_vu(db):
    return Voucher.objects.create(
        code='VU-ONCE',
        voucher_type=Voucher.TYPE_FIXED,
        discount_value=Decimal('50.00'),
        valid_from=timezone.now() - timedelta(days=1),
        is_active=True,
    )


class TestVoucherUsage:

    def test_voucher_used_twice_same_user_rejects_409(
        self, auth_client, user, prod_vu, voucher_vu, db
    ):
        """
        DEC-BC-10: si VoucherUsage ya existe para (user, voucher),
        el checkout devuelve 409 VOUCHER_ALREADY_USED_BY_USER.
        """
        # Simular que el usuario ya usó este voucher en un checkout anterior
        VoucherUsage.objects.create(user=user, voucher=voucher_vu)

        # Añadir item al carrito
        auth_client.post(ITEMS_URL, {'product_id': prod_vu.pk, 'quantity': 1}, format='json')

        # Aplicar voucher al carrito (CartVoucherView no revisa VoucherUsage)
        auth_client.post(CART_VOUCHER_URL, {'code': voucher_vu.code}, format='json')

        # Intentar checkout → debe rechazar con 409
        r = auth_client.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert r.status_code == 409
        assert r.json()['codigo_error'] == 'VOUCHER_ALREADY_USED_BY_USER'

    def test_current_uses_increments_atomic(
        self, auth_client, user, prod_vu, voucher_vu, db
    ):
        """
        DEC-BC-10: checkout exitoso con voucher incrementa current_uses
        y crea el registro VoucherUsage.
        """
        # Añadir item y aplicar voucher
        auth_client.post(ITEMS_URL, {'product_id': prod_vu.pk, 'quantity': 1}, format='json')
        auth_client.post(CART_VOUCHER_URL, {'code': voucher_vu.code}, format='json')

        # Checkout exitoso
        r = auth_client.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert r.status_code == 201

        # current_uses debe haberse incrementado a 1
        voucher_vu.refresh_from_db()
        assert voucher_vu.current_uses == 1

        # VoucherUsage debe existir para (user, voucher)
        assert VoucherUsage.objects.filter(user=user, voucher=voucher_vu).exists()
