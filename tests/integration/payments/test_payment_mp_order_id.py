"""
Tests — persistencia de mp_order_id (ORD) + gateway_payment_id (PAY) en Payment.

T-102 de la migración a Orders (DEC-ORD-03): el Payment guarda el id del recurso
Order de MP (ORD...) en mp_order_id y el id del pago anidado (PAY...) en
gateway_payment_id. Verifica el round-trip real contra MariaDB (kaupamex_qa).
"""
import pytest
from decimal import Decimal

from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from addons.payment.models import Payment

pytestmark = pytest.mark.integration


def _make_order(user):
    order = Order.objects.create(user=user, status='PENDING')
    OrderItem.objects.create(
        order=order, product_name='Prod ORD', sku='ORD-T102',
        unit_price=Decimal('200.00'), quantity=1, subtotal=Decimal('200.00'),
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('200.00'), tax=Decimal('0'),
        shipping_cost=Decimal('0'), discount=Decimal('0'), total=Decimal('200.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test', street='Calle ORD',
        city='CDMX', state='CMX', zip_code='06600',
    )
    return order


class TestMpOrderIdPersistence:
    def test_persists_both_ids(self, user, db):
        order = _make_order(user)
        payment = Payment.objects.create(
            order=order, gateway='MERCADOPAGO',
            mp_order_id='ORD01JABCDEF0123456789',
            gateway_payment_id='PAY86439942806',
            status=Payment.STATUS_APPROVED, amount=Decimal('200.00'),
        )
        reloaded = Payment.objects.get(pk=payment.pk)
        assert reloaded.mp_order_id == 'ORD01JABCDEF0123456789'
        assert reloaded.gateway_payment_id == 'PAY86439942806'

    def test_mp_order_id_optional_for_legacy(self, user, db):
        # Payments-legacy y PayPal no setean mp_order_id: debe aceptar null/blank.
        order = _make_order(user)
        payment = Payment.objects.create(
            order=order, gateway='PAYPAL',
            gateway_payment_id='PAYPAL-XYZ',
            status=Payment.STATUS_APPROVED, amount=Decimal('200.00'),
        )
        reloaded = Payment.objects.get(pk=payment.pk)
        assert reloaded.mp_order_id in (None, '')

    def test_mp_order_id_is_queryable(self, user, db):
        # db_index=True: se puede filtrar por mp_order_id (reconciliación webhook).
        order = _make_order(user)
        Payment.objects.create(
            order=order, gateway='MERCADOPAGO',
            mp_order_id='ORD-QUERYABLE-1',
            gateway_payment_id='PAY-Q1',
            status=Payment.STATUS_PENDING, amount=Decimal('200.00'),
        )
        found = Payment.objects.filter(mp_order_id='ORD-QUERYABLE-1').first()
        assert found is not None
        assert found.gateway_payment_id == 'PAY-Q1'
