"""Tests — V3a unificación orders→sale (``analisis-unificar-orders-sale``).

El eje de pago se ancla al canónico: en Odoo ``payment.transaction``
apunta a ``sale.order``; aquí ``Payment`` (la transacción strangler) gana
la FK ``sale_order`` y el espejo legacy ``orders.Order`` conoce su
canónico (``Order.sale_order``, fijado por ``confirm_draft_order``).
"""
import uuid
from decimal import Decimal

import pytest

from addons.catalogue.models import Category, Product
from addons.orders.models import Order
from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from addons.sale.services import add_item_to_draft, confirm_draft_order

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'Test V3a', 'street': 'Calle 1', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '06600',
}


@pytest.fixture
def product_v3(db):
    cat = Category.objects.create(name='Cat V3a', slug='cat-v3a', is_active=True)
    p = Product.objects.create(
        name='Prod V3a', slug='prod-v3a', sku='V3A-001', description='',
        price=Decimal('150.00'), stock=8, is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


def _confirmed_pair(product):
    """Confirma un draft anónimo y retorna (canónica, espejo legacy)."""
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid.uuid4())
    add_item_to_draft(draft, product, quantity=2)
    legacy = confirm_draft_order(draft, address_data=dict(ADDR),
                                 guest_email='v3a@test.mx')
    draft.refresh_from_db()
    return draft, legacy


class TestMirrorKnowsItsCanonical:
    def test_confirm_links_legacy_mirror_to_sale_order(self, product_v3):
        canonical, legacy = _confirmed_pair(product_v3)
        assert legacy.sale_order_id == canonical.pk
        assert canonical.legacy_order.pk == legacy.pk
        assert canonical.state == SaleOrder.STATE_SALE
        assert canonical.name and canonical.name.startswith('S-')
        assert legacy.status == Order.STATUS_PENDING

    def test_confirm_releases_cart_token_on_canonical(self, product_v3):
        canonical, _ = _confirmed_pair(product_v3)
        assert canonical.cart_token is None


class TestPaymentAnchorsToCanonical:
    def test_payment_carries_sale_order_fk(self, product_v3):
        canonical, legacy = _confirmed_pair(product_v3)
        payment = Payment.objects.create(
            order=legacy, sale_order=legacy.sale_order,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_PENDING, amount=Decimal('300.00'),
        )
        assert payment.sale_order_id == canonical.pk
        assert list(canonical.payments.all()) == [payment]

    def test_sale_order_fk_is_nullable_for_legacy_rows(self, product_v3):
        _, legacy = _confirmed_pair(product_v3)
        payment = Payment.objects.create(
            order=legacy, gateway=Payment.GATEWAY_MERCADOPAGO,
            status=Payment.STATUS_PENDING, amount=Decimal('300.00'),
        )
        assert payment.sale_order_id is None
