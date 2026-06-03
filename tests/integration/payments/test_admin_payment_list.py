"""
Tests — Listado de pagos admin (UC-PAY-11).

GET /api/v1/admin/payments/ — AdminPaymentListView (apps/payments/views.py).
Cubre: exito (lista + totales + paginacion), filtros (status, gateway,
rango de fechas), permisos (anon 401, comprador 403) y errores con
``codigo_error`` (status/gateway/fecha invalidos, rango invertido).
"""
import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model
from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.payments.models import Payment

pytestmark = pytest.mark.integration

LIST_URL = '/api/v1/admin/payments/'


def _make_order(user, sku, total):
    order = Order.objects.create(user=user, status='PROCESSING')
    OrderItem.objects.create(
        order=order, product_name='Prod', sku=sku,
        unit_price=total, quantity=1, subtotal=total,
    )
    OrderValue.objects.create(
        order=order, subtotal=total, tax=Decimal('0.00'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'), total=total,
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test',
        street='Calle 1', city='CDMX', state='CMX', zip_code='06600',
    )
    return order


@pytest.fixture
def payments_dataset(db, user):
    """Tres pagos: APPROVED, REFUNDED y FAILED en dos gateways."""
    cat = Category.objects.create(name='Cat Pay', slug='cat-pay', is_active=True)
    prod = Product.objects.create(
        name='Collar Eleggua', slug='collar-eleggua', sku='PAY-LIST-001',
        description='', price=Decimal('1000.00'), stock=10,
        is_active=True, is_published=True,
    )
    prod.categories.add(cat)

    o1 = _make_order(user, 'PAY-A', Decimal('1000.00'))
    p_approved = Payment.objects.create(
        order=o1, gateway='MERCADOPAGO', preference_id='PREF-A',
        gateway_payment_id='MP-A', status='APPROVED', amount=Decimal('1000.00'),
    )
    o2 = _make_order(user, 'PAY-B', Decimal('500.00'))
    p_refunded = Payment.objects.create(
        order=o2, gateway='PAYPAL', preference_id='PREF-B',
        gateway_payment_id='PP-B', status='REFUNDED', amount=Decimal('500.00'),
    )
    o3 = _make_order(user, 'PAY-C', Decimal('250.00'))
    p_failed = Payment.objects.create(
        order=o3, gateway='MERCADOPAGO', preference_id='PREF-C',
        gateway_payment_id='MP-C', status='FAILED', amount=Decimal('250.00'),
    )
    return {'approved': p_approved, 'refunded': p_refunded, 'failed': p_failed}


class TestAdminPaymentList:

    # --- permisos ---
    def test_anon_recibe_401(self, api_client, db):
        r = api_client.get(LIST_URL)
        assert r.status_code == 401

    def test_comprador_recibe_403(self, auth_client, db):
        r = auth_client.get(LIST_URL)
        assert r.status_code == 403

    # --- exito: lista + paginacion + totales ---
    def test_admin_lista_pagos_con_totales(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL)
        assert r.status_code == 200
        data = r.json()
        # Paginacion DRF: count + results; totales inyectados por la view.
        assert data['count'] == 3
        assert len(data['results']) == 3
        assert 'totals' in data
        # approved=1000, refunded=500, net=500
        assert Decimal(str(data['totals']['approved'])) == Decimal('1000.00')
        assert Decimal(str(data['totals']['refunded'])) == Decimal('500.00')
        assert Decimal(str(data['totals']['net'])) == Decimal('500.00')

    def test_serializer_incluye_campos_admin(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL)
        results = r.json()['results']
        # AdminPaymentSerializer agrega order_status y user_email.
        assert all('order_status' in row for row in results)
        assert all('user_email' in row for row in results)

    # --- filtros ---
    def test_filtro_por_status(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL, {'status': 'APPROVED'})
        assert r.status_code == 200
        data = r.json()
        assert data['count'] == 1
        assert data['results'][0]['status'] == 'APPROVED'

    def test_filtro_por_gateway(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL, {'gateway': 'PAYPAL'})
        assert r.status_code == 200
        data = r.json()
        assert data['count'] == 1
        assert data['results'][0]['gateway'] == 'PAYPAL'

    def test_filtro_gateway_lowercase_se_normaliza(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL, {'gateway': 'paypal'})
        assert r.status_code == 200
        assert r.json()['count'] == 1

    # --- errores con codigo_error ---
    def test_status_invalido_400(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL, {'status': 'NOPE'})
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_STATUS'

    def test_gateway_invalido_400(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL, {'gateway': 'STRIPE'})
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_GATEWAY'

    def test_fecha_invalida_400(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL, {'from': '2026-13-99'})
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_DATE_FORMAT'

    def test_rango_invertido_400(self, admin_client, payments_dataset):
        r = admin_client.get(LIST_URL, {'from': '2026-06-01', 'to': '2026-01-01'})
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_DATE_RANGE'
