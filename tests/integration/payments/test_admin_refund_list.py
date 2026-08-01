"""
Tests — Listado de reembolsos por pago (T-16-D, UC-PAY-09).

GET /api/v2/admin/payments/<id>/refunds/ — AdminPaymentRefundsListView.
Cubre: lista completa, pago sin reembolsos, permisos (401/403), 404.
"""
from addons.sale.models import SaleOrderLine
import pytest
from decimal import Decimal

from addons.catalogue.models import Category, Product
from addons.payment.models import Payment, Refund
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration

REFUNDS_URL = lambda pid: f'/api/v2/admin/payments/{pid}/refunds/'


def _make_payment(user, amount='500.00', status='APPROVED', gateway_payment_id='MP-001'):
    # PROCESSING es un valor muerto de la proyección; PENDING deja la orden
    # confirmada sin que el factory cree su propio Payment, para no chocar
    # con el Payment manual de abajo. El subtotal ya no vive en el espejo
    # ``OrderValue`` (retirado, SOL-098): lo reproduce la línea de producto.
    # ``Payment.sale_order`` es la única FK.
    cat, _ = Category.objects.get_or_create(
        slug='cat-rfl', defaults={'name': 'Cat RFL', 'is_active': True},
    )
    prod = Product.objects.create(
        name='Eleke', slug=f'eleke-{gateway_payment_id.lower()}',
        sku=gateway_payment_id,
        description='', price=Decimal(amount), stock=10,
        is_active=True, is_published=True,
    )
    prod.categories.add(cat)
    order = make_order(user=user, status='PENDING')
    SaleOrderLine.objects.create(
        order=order, product=prod, name='Eleke',
        price_unit=Decimal(amount), product_uom_qty=1,
    )
    DeliveryAddress.objects.create(
        sale_order=order, recipient_name='Test',
        street='Calle 1', city='CDMX', state='CMX', zip_code='06600',
    )
    return Payment.objects.create(
        sale_order=order, gateway='MERCADOPAGO',
        preference_id='PREF-RFL', gateway_payment_id=gateway_payment_id,
        status=status, amount=Decimal(amount),
    )


@pytest.fixture
def payment_with_refunds(db, user):
    pay = _make_payment(user, '500.00', 'REFUNDED', 'MP-RFL-001')
    Refund.objects.create(
        payment=pay, amount=Decimal('200.00'), reason='Devolucion parcial',
        gateway_refund_id='REF-001', status=Refund.STATUS_APPROVED,
    )
    Refund.objects.create(
        payment=pay, amount=Decimal('300.00'), reason='Devolucion restante',
        gateway_refund_id='REF-002', status=Refund.STATUS_APPROVED,
    )
    return pay


class TestAdminPaymentRefundsList:

    def test_returns_refunds_for_payment(self, admin_client, payment_with_refunds):
        resp = admin_client.get(REFUNDS_URL(payment_with_refunds.pk))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        amounts = {item['amount'] for item in data}
        assert amounts == {'200.00', '300.00'}

    def test_response_includes_gateway_refund_id(self, admin_client, payment_with_refunds):
        resp = admin_client.get(REFUNDS_URL(payment_with_refunds.pk))
        ids = {item['gateway_refund_id'] for item in resp.json()}
        assert ids == {'REF-001', 'REF-002'}

    def test_empty_list_when_no_refunds(self, admin_client, user, db):
        pay = _make_payment(user, '100.00', 'APPROVED', 'MP-EMPTY')
        resp = admin_client.get(REFUNDS_URL(pay.pk))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_404_for_unknown_payment(self, admin_client, db):
        resp = admin_client.get(REFUNDS_URL(99999))
        assert resp.status_code == 404

    def test_requires_authentication(self, api_client, payment_with_refunds):
        resp = api_client.get(REFUNDS_URL(payment_with_refunds.pk))
        assert resp.status_code == 401

    def test_requires_admin(self, auth_client, payment_with_refunds):
        resp = auth_client.get(REFUNDS_URL(payment_with_refunds.pk))
        assert resp.status_code == 403
