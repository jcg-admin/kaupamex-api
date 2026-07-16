"""Tests — VOUCHER_ALREADY_APPLIED 409 in CartVoucherView (DEC-BC-20)."""
import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.addons.catalogue.models import Category, Product
from apps.addons.voucher.models import Voucher

pytestmark = pytest.mark.integration

VOUCHER_URL = '/api/v2/cart/voucher/'
ITEMS_URL   = '/api/v2/cart/items/'


@pytest.fixture
def cat_vch(db):
    return Category.objects.create(name='Cat Vch', slug='cat-vch', is_active=True)


@pytest.fixture
def prod_vch(db, cat_vch):
    _p = Product.objects.create(
        name='Prod Vch', slug='prod-vch', sku='VCH-001',
        description='',
        price=Decimal('300.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_vch)
    return _p


@pytest.fixture
def cart_vch(auth_client, prod_vch):
    auth_client.post(ITEMS_URL, {'product_id': prod_vch.pk, 'quantity': 1}, format='json')
    return auth_client


@pytest.fixture
def voucher_a(db, admin_user):
    return Voucher.objects.create(
        code='VCH-A', voucher_type='FIXED',
        discount_value=Decimal('50.00'),
        valid_from=timezone.now() - timedelta(days=1),
        is_active=True, min_order_amount=Decimal('0'),
        created_by=admin_user,
    )


@pytest.fixture
def voucher_b(db, admin_user):
    return Voucher.objects.create(
        code='VCH-B', voucher_type='FIXED',
        discount_value=Decimal('30.00'),
        valid_from=timezone.now() - timedelta(days=1),
        is_active=True, min_order_amount=Decimal('0'),
        created_by=admin_user,
    )


class TestVoucherAlreadyApplied:

    def test_second_voucher_returns_409(self, cart_vch, voucher_a, voucher_b):
        cart_vch.post(VOUCHER_URL, {'code': 'VCH-A'}, format='json')
        r = cart_vch.post(VOUCHER_URL, {'code': 'VCH-B'}, format='json')
        assert r.status_code == 409

    def test_second_voucher_error_code(self, cart_vch, voucher_a, voucher_b):
        cart_vch.post(VOUCHER_URL, {'code': 'VCH-A'}, format='json')
        r = cart_vch.post(VOUCHER_URL, {'code': 'VCH-B'}, format='json')
        assert r.json().get('codigo_error') == 'VOUCHER_ALREADY_APPLIED'

    def test_same_voucher_twice_returns_409(self, cart_vch, voucher_a):
        cart_vch.post(VOUCHER_URL, {'code': 'VCH-A'}, format='json')
        r = cart_vch.post(VOUCHER_URL, {'code': 'VCH-A'}, format='json')
        assert r.status_code == 409
        assert r.json().get('codigo_error') == 'VOUCHER_ALREADY_APPLIED'

    def test_remove_then_apply_succeeds(self, cart_vch, voucher_a):
        cart_vch.post(VOUCHER_URL, {'code': 'VCH-A'}, format='json')
        cart_vch.delete(VOUCHER_URL)
        r = cart_vch.post(VOUCHER_URL, {'code': 'VCH-A'}, format='json')
        assert r.status_code == 200

    def test_first_application_succeeds(self, cart_vch, voucher_a):
        r = cart_vch.post(VOUCHER_URL, {'code': 'VCH-A'}, format='json')
        assert r.status_code == 200
