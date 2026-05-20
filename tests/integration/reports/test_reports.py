"""
Tests — Reports aggregation endpoints

UC-REP-01: Sales report
UC-REP-02: Top sellers report
UC-REP-03: Dashboard snapshot
UC-REP-04: RFM customer segmentation
UC-REP-05: Report export (CSV/PDF)

DEC-DOC-005: English identifiers and English JSON keys.
"""
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.catalogue.models import Category, Product
from django.contrib.auth import get_user_model
from apps.orders.models import Order, OrderItem, OrderValue
from apps.payments.models import Payment
from apps.support.models import SupportTicket

import pytest

pytestmark = pytest.mark.integration

BASE = '/api/v1/admin/reports/'


def _now():
    return timezone.now()


@pytest.fixture
def category(db):
    return Category.objects.create(name='Rep Cat', slug='rep-cat', is_active=True)


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        name='Rep Prod', slug='rep-prod', sku='REP-001',
        description='', category=category,
        price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def product_b(db, category):
    return Product.objects.create(
        name='Rep Prod B', slug='rep-prod-b', sku='REP-002',
        description='', category=category,
        price=Decimal('300.00'), stock=5,
        is_active=True, is_published=True,
    )


@pytest.fixture
def buyer(db):
    User = get_user_model()
    return User.objects.create_user(
        username='buyer1', email='b1@x.com', password='Pass123!',
    )


@pytest.fixture
def buyer_b(db):
    User = get_user_model()
    return User.objects.create_user(
        username='buyer2', email='b2@x.com', password='Pass123!',
    )


def _make_order(user, product, qty=1, when=None, status='DELIVERED',
                gateway='MERCADOPAGO', payment_status='APPROVED'):
    when = when or _now()
    o = Order.objects.create(user=user, status=status)
    Order.objects.filter(pk=o.pk).update(created_at=when, updated_at=when)
    OrderItem.objects.create(
        order=o, product=product,
        product_name=product.name, sku=product.sku,
        unit_price=product.price, quantity=qty,
        subtotal=product.price * qty,
    )
    total = product.price * qty
    OrderValue.objects.create(
        order=o, subtotal=total, tax=Decimal('0'),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=total,
    )
    p = Payment.objects.create(
        order=o, gateway=gateway, status=payment_status,
        amount=total,
    )
    Payment.objects.filter(pk=p.pk).update(created_at=when, updated_at=when)
    return o


# =============================================================================
# UC-REP-01 — Sales report
# =============================================================================
class TestSalesReport:

    def test_sales_returns_200(self, admin_client, product, buyer):
        _make_order(buyer, product)
        res = admin_client.get(f'{BASE}sales/?period=30d')
        assert res.status_code == 200
        body = res.json()
        assert 'totals' in body
        assert 'comparison' in body
        assert 'series' in body
        assert 'payment_breakdown' in body

    def test_sales_totals_aggregate(self, admin_client, product, buyer):
        _make_order(buyer, product, qty=2)
        _make_order(buyer, product, qty=1)
        res = admin_client.get(f'{BASE}sales/?period=30d')
        body = res.json()
        # 2 orders, total: 2*500 + 1*500 = 1500
        assert Decimal(body['totals']['revenue']) == Decimal('1500.00')
        assert body['totals']['orders'] == 2

    def test_sales_payment_breakdown(self, admin_client, product, buyer):
        _make_order(buyer, product, gateway='MERCADOPAGO')
        _make_order(buyer, product, gateway='PAYPAL')
        res = admin_client.get(f'{BASE}sales/?period=30d')
        body = res.json()
        gateways = {row['gateway']: row for row in body['payment_breakdown']}
        assert 'MERCADOPAGO' in gateways
        assert 'PAYPAL' in gateways

    def test_sales_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}sales/?period=30d')
        assert res.status_code in (401, 403)

    def test_sales_requires_auth(self, api_client, db):
        res = api_client.get(f'{BASE}sales/?period=30d')
        assert res.status_code == 401


# =============================================================================
# UC-REP-02 — Top sellers
# =============================================================================
class TestTopSellers:

    def test_top_sellers_returns_200(self, admin_client, product, product_b, buyer):
        _make_order(buyer, product, qty=5)
        _make_order(buyer, product_b, qty=1)
        res = admin_client.get(f'{BASE}top-sellers/?period=30d&limit=10')
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        assert 'inactive_no_sales_pct' in body

    def test_top_sellers_ordered_by_units(self, admin_client, product, product_b, buyer):
        _make_order(buyer, product, qty=5)
        _make_order(buyer, product_b, qty=1)
        res = admin_client.get(f'{BASE}top-sellers/?period=30d&limit=10')
        rows = res.json()['results']
        assert rows[0]['product_id'] == product.pk
        assert rows[0]['units_sold'] == 5

    def test_top_sellers_respects_limit(self, admin_client, product, product_b, buyer):
        _make_order(buyer, product, qty=5)
        _make_order(buyer, product_b, qty=1)
        res = admin_client.get(f'{BASE}top-sellers/?period=30d&limit=1')
        rows = res.json()['results']
        assert len(rows) == 1

    def test_top_sellers_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}top-sellers/?period=30d')
        assert res.status_code in (401, 403)


# =============================================================================
# UC-REP-03 — Dashboard
# =============================================================================
class TestDashboard:

    def test_dashboard_returns_200(self, admin_client, product, buyer):
        _make_order(buyer, product)
        res = admin_client.get(f'{BASE}dashboard/')
        assert res.status_code == 200
        body = res.json()
        assert 'today' in body
        assert 'trend' in body
        assert 'top_products' in body
        assert 'open_tickets' in body
        assert 'low_stock_alerts' in body

    def test_dashboard_today_counts_orders(self, admin_client, product, buyer):
        _make_order(buyer, product)
        _make_order(buyer, product, qty=2)
        res = admin_client.get(f'{BASE}dashboard/')
        body = res.json()
        assert body['today']['orders'] >= 2

    def test_dashboard_open_tickets(self, admin_client, product, buyer):
        SupportTicket.objects.create(
            user=buyer, subject='Hello world there', body='Need help with order',
            status='OPEN',
        )
        res = admin_client.get(f'{BASE}dashboard/')
        assert res.json()['open_tickets'] >= 1

    def test_dashboard_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}dashboard/')
        assert res.status_code in (401, 403)


# =============================================================================
# UC-REP-04 — Customers RFM
# =============================================================================
class TestCustomersRFM:

    def test_rfm_returns_200(self, admin_client, product, buyer):
        _make_order(buyer, product)
        res = admin_client.get(f'{BASE}customers-rfm/?period=90d')
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        assert 'totals' in body

    def test_rfm_contains_buyer(self, admin_client, product, buyer):
        _make_order(buyer, product, qty=3)
        res = admin_client.get(f'{BASE}customers-rfm/?period=90d')
        rows = res.json()['results']
        ids = [r['user_id'] for r in rows]
        assert buyer.pk in ids

    def test_rfm_segment_filter(self, admin_client, product, buyer, buyer_b):
        _make_order(buyer, product, qty=10)
        _make_order(buyer_b, product, qty=1)
        # Just ensure ?segment= is accepted without 5xx
        res = admin_client.get(f'{BASE}customers-rfm/?period=90d&segment=CHAMPIONS')
        assert res.status_code == 200

    def test_rfm_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}customers-rfm/?period=90d')
        assert res.status_code in (401, 403)


# =============================================================================
# UC-REP-05 — Export
# =============================================================================
class TestExport:

    def test_export_sales_csv(self, admin_client, product, buyer):
        _make_order(buyer, product)
        res = admin_client.get(f'{BASE}sales/export/?period=30d&format=csv')
        assert res.status_code == 200
        assert 'text/csv' in res['Content-Type']
        assert 'attachment' in res['Content-Disposition']
        assert '.csv' in res['Content-Disposition']

    def test_export_top_sellers_csv(self, admin_client, product, buyer):
        _make_order(buyer, product)
        res = admin_client.get(f'{BASE}top-sellers/export/?period=30d&format=csv')
        assert res.status_code == 200
        assert 'text/csv' in res['Content-Type']

    def test_export_unknown_slug_returns_404(self, admin_client, db):
        res = admin_client.get(f'{BASE}bogus/export/?format=csv')
        assert res.status_code == 404

    def test_export_unsupported_format_returns_400(self, admin_client, product, buyer):
        _make_order(buyer, product)
        res = admin_client.get(f'{BASE}sales/export/?format=xml')
        assert res.status_code == 400

    def test_export_pdf_returns_200(self, admin_client, product, buyer):
        _make_order(buyer, product)
        res = admin_client.get(f'{BASE}sales/export/?period=30d&format=pdf')
        # PDF support may be minimal (text/plain placeholder is OK as long as 200)
        assert res.status_code == 200
        assert 'attachment' in res['Content-Disposition']

    def test_export_requires_admin(self, auth_client, db):
        res = auth_client.get(f'{BASE}sales/export/?format=csv')
        assert res.status_code in (401, 403)
