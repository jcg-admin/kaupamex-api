"""
Tests — persistencia de mp_order_id (ORD) + gateway_payment_id (PAY) en Payment.

T-102 de la migración a Orders (DEC-ORD-03): el Payment guarda el id del recurso
SaleOrder de MP (ORD...) en mp_order_id y el id del pago anidado (PAY...) en
gateway_payment_id. Verifica el round-trip real contra MariaDB (kaupamex_qa).
"""
import pytest
from uuid import uuid4
from addons.catalogue.models import Category, Product
from addons.delivery.models import DeliveryAddress
from decimal import Decimal

from addons.payment.models import Payment
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration


def _make_order(user):
    """Crea una orden PENDING con una línea de producto (subtotal 200.00).

    El registro de importes aparte de la orden se retiró con el espejo
    (SOL-098): el importe se recalcula desde ``order_line``, no se fija a
    mano. El producto es mínimo y local a la llamada (este módulo no
    comparte fixtures de catálogo con los demás archivos de payments).
    """
    suffix = uuid4().hex[:8]
    category = Category.objects.create(
        name=f'Cat ORD {suffix}', slug=f'cat-ord-{suffix}', is_active=True,
    )
    product = Product.objects.create(
        name='Prod ORD', slug=f'prod-ord-{suffix}', sku=f'ORD-{suffix}',
        description='', price=Decimal('200.00'), stock=10,
        is_active=True, is_published=True,
    )
    product.categories.add(category)
    order = make_order(user=user, status='PENDING', product=product, quantity=1)
    DeliveryAddress.objects.create(
        sale_order=order, recipient_name='Test', street='Calle ORD',
        city='CDMX', state='CMX', zip_code='06600',
    )
    return order


class TestMpOrderIdPersistence:
    def test_persists_both_ids(self, user, db):
        order = _make_order(user)
        payment = Payment.objects.create(
            sale_order=order, gateway='MERCADOPAGO',
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
            sale_order=order, gateway='PAYPAL',
            gateway_payment_id='PAYPAL-XYZ',
            status=Payment.STATUS_APPROVED, amount=Decimal('200.00'),
        )
        reloaded = Payment.objects.get(pk=payment.pk)
        assert reloaded.mp_order_id in (None, '')

    def test_mp_order_id_is_queryable(self, user, db):
        # db_index=True: se puede filtrar por mp_order_id (reconciliación webhook).
        order = _make_order(user)
        Payment.objects.create(
            sale_order=order, gateway='MERCADOPAGO',
            mp_order_id='ORD-QUERYABLE-1',
            gateway_payment_id='PAY-Q1',
            status=Payment.STATUS_PENDING, amount=Decimal('200.00'),
        )
        found = Payment.objects.filter(mp_order_id='ORD-QUERYABLE-1').first()
        assert found is not None
        assert found.gateway_payment_id == 'PAY-Q1'
