"""
Tests — Product discount management

UC-DASH-01: List product discounts (with optional status filter)
UC-DASH-02: Create product discount
UC-DASH-03: Edit product discount
UC-DASH-04: Deactivate product discount

DEC-DOC-005: English identifiers and English JSON keys.
"""
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.modules.catalogue.models import Category, Product, ProductDiscount

import pytest

pytestmark = pytest.mark.integration

URL = '/api/v2/admin/product-discounts/'


def _now():
    return timezone.now()


def _past(**kw):
    return _now() - timedelta(**kw)


def _future(**kw):
    return _now() + timedelta(**kw)


@pytest.fixture
def category(db):
    return Category.objects.create(name='Discount Cat', slug='discount-cat', is_active=True)


@pytest.fixture
def product(db, category):
    _p = Product.objects.create(
        name='Discounted Prod', slug='discounted-prod', sku='DISC-001',
        description='',
        price=Decimal('1000.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(category)
    return _p


@pytest.fixture
def product_b(db, category):
    _p = Product.objects.create(
        name='Other Prod', slug='other-prod', sku='OTHER-001',
        description='',
        price=Decimal('500.00'), stock=5,
        is_active=True, is_published=True,
    )
    _p.categories.add(category)
    return _p


@pytest.fixture
def current_discount(db, product, admin_user):
    return ProductDiscount.objects.create(
        product=product,
        discount_pct=Decimal('20.00'),
        valid_from=_past(days=1),
        valid_until=_future(days=10),
        is_active=True,
        created_by=admin_user,
    )


# =============================================================================
# UC-DASH-01 — list product discounts
# =============================================================================
class TestListProductDiscounts:

    def test_list_returns_200_with_results(self, admin_client, current_discount):
        res = admin_client.get(URL)
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        assert len(body['results']) == 1
        row = body['results'][0]
        assert row['product_id'] == current_discount.product_id
        assert row['product_name'] == current_discount.product.name
        assert Decimal(row['discount_pct']) == Decimal('20.00')
        assert row['status'] == 'CURRENT'
        assert row['is_active'] is True
        assert Decimal(row['original_price']) == Decimal('1000.00')
        assert Decimal(row['discounted_price']) == Decimal('800.00')

    def test_list_filter_by_status_current(self, admin_client, product, product_b, admin_user):
        ProductDiscount.objects.create(
            product=product, discount_pct=Decimal('10'),
            valid_from=_past(days=1), valid_until=_future(days=10),
            is_active=True, created_by=admin_user,
        )
        ProductDiscount.objects.create(
            product=product_b, discount_pct=Decimal('15'),
            valid_from=_future(days=5), valid_until=_future(days=20),
            is_active=True, created_by=admin_user,
        )
        res = admin_client.get(URL + '?status=CURRENT')
        assert res.status_code == 200
        rows = res.json()['results']
        assert len(rows) == 1
        assert rows[0]['status'] == 'CURRENT'

    def test_list_filter_by_status_future(self, admin_client, product, admin_user):
        ProductDiscount.objects.create(
            product=product, discount_pct=Decimal('15'),
            valid_from=_future(days=5), valid_until=_future(days=20),
            is_active=True, created_by=admin_user,
        )
        res = admin_client.get(URL + '?status=FUTURE')
        assert res.status_code == 200
        rows = res.json()['results']
        assert len(rows) == 1
        assert rows[0]['status'] == 'FUTURE'

    def test_list_filter_by_status_expired(self, admin_client, product, admin_user):
        ProductDiscount.objects.create(
            product=product, discount_pct=Decimal('15'),
            valid_from=_past(days=10), valid_until=_past(days=1),
            is_active=True, created_by=admin_user,
        )
        res = admin_client.get(URL + '?status=EXPIRED')
        assert res.status_code == 200
        rows = res.json()['results']
        assert len(rows) == 1
        assert rows[0]['status'] == 'EXPIRED'

    def test_list_requires_auth(self, api_client, db):
        res = api_client.get(URL)
        assert res.status_code == 401

    def test_list_requires_admin(self, auth_client, db):
        res = auth_client.get(URL)
        assert res.status_code in (401, 403)


# =============================================================================
# UC-DASH-02 — create product discount
# =============================================================================
class TestCreateProductDiscount:

    def test_create_returns_201(self, admin_client, product):
        res = admin_client.post(URL, {
            'product_id': product.pk,
            'discount_pct': '25.00',
            'valid_from': _past(days=1).isoformat(),
            'valid_until': _future(days=10).isoformat(),
        }, format='json')
        assert res.status_code == 201
        body = res.json()
        assert body['product_id'] == product.pk
        assert Decimal(body['discount_pct']) == Decimal('25.00')
        assert body['status'] == 'CURRENT'

    def test_create_with_null_valid_until(self, admin_client, product):
        res = admin_client.post(URL, {
            'product_id': product.pk,
            'discount_pct': '10.00',
            'valid_from': _past(days=1).isoformat(),
            'valid_until': None,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['valid_until'] is None
        assert res.json()['status'] == 'CURRENT'

    def test_create_conflict_when_active_discount_exists(self, admin_client, current_discount, product):
        res = admin_client.post(URL, {
            'product_id': product.pk,
            'discount_pct': '15.00',
            'valid_from': _past(days=1).isoformat(),
            'valid_until': _future(days=5).isoformat(),
        }, format='json')
        assert res.status_code == 409
        assert res.json()['codigo_error'] == 'ACTIVE_DISCOUNT_EXISTS'

    def test_create_unknown_product_returns_422(self, admin_client, db):
        res = admin_client.post(URL, {
            'product_id': 999999,
            'discount_pct': '15.00',
            'valid_from': _past(days=1).isoformat(),
        }, format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'PRODUCT_UNAVAILABLE'

    def test_create_inactive_product_returns_422(self, admin_client, product):
        product.is_active = False
        product.save()
        res = admin_client.post(URL, {
            'product_id': product.pk,
            'discount_pct': '15.00',
            'valid_from': _past(days=1).isoformat(),
        }, format='json')
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'PRODUCT_UNAVAILABLE'

    def test_create_invalid_pct_returns_400(self, admin_client, product):
        res = admin_client.post(URL, {
            'product_id': product.pk,
            'discount_pct': '150.00',
            'valid_from': _past(days=1).isoformat(),
        }, format='json')
        assert res.status_code == 400

    def test_create_requires_auth(self, api_client, product):
        res = api_client.post(URL, {
            'product_id': product.pk,
            'discount_pct': '10.00',
            'valid_from': _past(days=1).isoformat(),
        }, format='json')
        assert res.status_code == 401


# =============================================================================
# UC-DASH-03 — edit product discount
# =============================================================================
class TestEditProductDiscount:

    def test_patch_updates_pct(self, admin_client, current_discount):
        res = admin_client.patch(
            f'{URL}{current_discount.pk}/',
            {'discount_pct': '35.00'}, format='json',
        )
        assert res.status_code == 200
        assert Decimal(res.json()['discount_pct']) == Decimal('35.00')

    def test_patch_updates_dates(self, admin_client, current_discount):
        new_until = _future(days=30).isoformat()
        res = admin_client.patch(
            f'{URL}{current_discount.pk}/',
            {'valid_until': new_until}, format='json',
        )
        assert res.status_code == 200

    def test_patch_invalid_date_range_returns_422(self, admin_client, current_discount):
        res = admin_client.patch(
            f'{URL}{current_discount.pk}/',
            {'valid_from': _future(days=10).isoformat(),
             'valid_until': _future(days=5).isoformat()},
            format='json',
        )
        assert res.status_code == 422
        assert res.json()['codigo_error'] == 'INVALID_DATE_RANGE'

    def test_patch_unknown_returns_404(self, admin_client, db):
        res = admin_client.patch(f'{URL}999999/', {'discount_pct': '10'}, format='json')
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'DISCOUNT_NOT_APPLICABLE'

    def test_patch_cannot_change_product(self, admin_client, current_discount, product_b):
        """product_id is immutable."""
        old_product_id = current_discount.product_id
        res = admin_client.patch(
            f'{URL}{current_discount.pk}/',
            {'product_id': product_b.pk}, format='json',
        )
        # Either 400 or silently ignored; assert product_id unchanged
        current_discount.refresh_from_db()
        assert current_discount.product_id == old_product_id

    def test_patch_requires_auth(self, api_client, current_discount):
        res = api_client.patch(
            f'{URL}{current_discount.pk}/', {'discount_pct': '10'}, format='json',
        )
        assert res.status_code == 401


# =============================================================================
# UC-DASH-04 — deactivate product discount
# =============================================================================
class TestDeactivateProductDiscount:

    def test_deactivate_returns_200(self, admin_client, current_discount):
        res = admin_client.patch(
            f'{URL}{current_discount.pk}/', {'active': False}, format='json'
        )
        assert res.status_code == 200
        body = res.json()
        assert body['is_active'] is False
        current_discount.refresh_from_db()
        assert current_discount.is_active is False
        assert current_discount.deactivated_at is not None
        assert current_discount.deactivated_by is not None

    def test_deactivate_already_inactive_returns_409(self, admin_client, current_discount):
        current_discount.is_active = False
        current_discount.save()
        res = admin_client.patch(
            f'{URL}{current_discount.pk}/', {'active': False}, format='json'
        )
        assert res.status_code == 409
        assert res.json()['codigo_error'] == 'DISCOUNT_ALREADY_INACTIVE'

    def test_deactivate_unknown_returns_404(self, admin_client, db):
        res = admin_client.patch(f'{URL}999999/', {'active': False}, format='json')
        assert res.status_code == 404

    def test_deactivate_requires_admin(self, auth_client, current_discount):
        res = auth_client.patch(
            f'{URL}{current_discount.pk}/', {'active': False}, format='json'
        )
        assert res.status_code in (401, 403)

    def test_after_deactivate_can_create_new(self, admin_client, current_discount, product):
        admin_client.patch(f'{URL}{current_discount.pk}/', {'active': False}, format='json')
        res = admin_client.post(URL, {
            'product_id': product.pk,
            'discount_pct': '5.00',
            'valid_from': _past(days=1).isoformat(),
            'valid_until': _future(days=5).isoformat(),
        }, format='json')
        assert res.status_code == 201
