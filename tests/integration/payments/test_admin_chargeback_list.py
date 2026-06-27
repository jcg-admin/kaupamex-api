"""
Tests — Listado y detalle de contracargos admin (T-17-B, T-17-C).

GET /api/v1/admin/chargebacks/        — AdminChargebackListView
GET /api/v1/admin/chargebacks/<id>/   — AdminChargebackDetailView
Cubre: lista, detalle, filtro por payment, 401, 403, 404.
"""
import pytest
from decimal import Decimal

from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.payments.models import Payment, Chargeback

pytestmark = pytest.mark.integration

LIST_URL   = '/api/v1/admin/chargebacks/'
DETAIL_URL = lambda cid: f'/api/v1/admin/chargebacks/{cid}/'


def _make_payment(user, amount='500.00', gateway_payment_id='MP-CB-L001'):
    order = Order.objects.create(user=user, status='PROCESSING')
    OrderItem.objects.create(
        order=order, product_name='Prod CB', sku=f'CB-{gateway_payment_id}',
        unit_price=Decimal(amount), quantity=1, subtotal=Decimal(amount),
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal(amount), tax=Decimal('0'),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=Decimal(amount),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test', street='Calle CB',
        city='CDMX', state='CMX', zip_code='06600',
    )
    return Payment.objects.create(
        order=order, gateway='MERCADOPAGO',
        preference_id=f'PREF-{gateway_payment_id}',
        gateway_payment_id=gateway_payment_id,
        status=Payment.STATUS_APPROVED, amount=Decimal(amount),
    )


@pytest.fixture
def chargeback_dataset(db, user):
    p1 = _make_payment(user, '500.00', 'MP-CB-A')
    p2 = _make_payment(user, '300.00', 'MP-CB-B')
    cb1 = Chargeback.objects.create(
        payment=p1, gateway_chargeback_id='GCB-001',
        gateway_payment_id='MP-CB-A', amount=Decimal('500.00'),
        status=Chargeback.STATUS_PENDING, reason_code='chargeback_fraud',
    )
    cb2 = Chargeback.objects.create(
        payment=p2, gateway_chargeback_id='GCB-002',
        gateway_payment_id='MP-CB-B', amount=Decimal('300.00'),
        status=Chargeback.STATUS_LOST, reason_code='chargeback_no_response',
    )
    return [cb1, cb2]


class TestAdminChargebackList:

    def test_returns_all_chargebacks(self, admin_client, chargeback_dataset):
        resp = admin_client.get(LIST_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_response_includes_key_fields(self, admin_client, chargeback_dataset):
        resp = admin_client.get(LIST_URL)
        item = resp.json()[0]
        for field in ('id', 'gateway_chargeback_id', 'gateway_payment_id',
                      'amount', 'status', 'reason_code'):
            assert field in item, f'Missing field: {field}'

    def test_filter_by_status(self, admin_client, chargeback_dataset):
        resp = admin_client.get(LIST_URL, {'status': Chargeback.STATUS_LOST})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['gateway_chargeback_id'] == 'GCB-002'

    def test_requires_authentication(self, api_client, chargeback_dataset):
        resp = api_client.get(LIST_URL)
        assert resp.status_code == 401

    def test_requires_admin(self, auth_client, chargeback_dataset):
        resp = auth_client.get(LIST_URL)
        assert resp.status_code == 403


class TestAdminChargebackDetail:

    def test_returns_chargeback_detail(self, admin_client, chargeback_dataset):
        cb = chargeback_dataset[0]
        resp = admin_client.get(DETAIL_URL(cb.pk))
        assert resp.status_code == 200
        data = resp.json()
        assert data['gateway_chargeback_id'] == 'GCB-001'
        assert data['amount'] == '500.00'

    def test_returns_404_for_unknown(self, admin_client, db):
        resp = admin_client.get(DETAIL_URL(99999))
        assert resp.status_code == 404

    def test_requires_authentication(self, api_client, chargeback_dataset):
        cb = chargeback_dataset[0]
        resp = api_client.get(DETAIL_URL(cb.pk))
        assert resp.status_code == 401

    def test_requires_admin(self, auth_client, chargeback_dataset):
        cb = chargeback_dataset[0]
        resp = auth_client.get(DETAIL_URL(cb.pk))
        assert resp.status_code == 403
