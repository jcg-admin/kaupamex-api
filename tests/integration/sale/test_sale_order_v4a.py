"""Tests — V4a unificación orders→sale (``analisis-unificar-orders-sale``).

Post-venta y logística anclan al canónico: ``rating.Review`` (prueba de
compra UC-REV-02) y ``delivery.ShipmentGuide`` (el eje de fulfillment,
adaptación de ``stock.picking``) tienen FK ``sale_order`` directa a la venta.

Post-E5 (retiro del addon espejo ``orders``, ``api@77bd1f0``): la venta ES la
orden — no hay un segundo objeto ``.sale_order`` que enlazar; ``Review`` y
``ShipmentGuide`` sólo declaran ``sale_order`` (verificado:
``src/addons/rating/models/review.py:55`` y
``src/addons/delivery/models/__init__.py:129``, ninguno tiene ya ``order``).
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.delivery.models import Courier, ShipmentGuide
from addons.rating.models import Review
from addons.sale.models import SaleOrder
from addons.sale.services import add_item_to_draft, confirm_draft_order
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.django_db

User = get_user_model()

ADDR = {
    'recipient_name': 'Test V4a', 'street': 'Calle 2', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '06600',
}


@pytest.fixture
def product_v4(db):
    cat = make_category(name='Cat V4a')
    return make_product(name='Prod V4a', price=Decimal('120.00'), stock=6, categ=cat)


@pytest.fixture
def confirmed_order(product_v4):
    user = User.objects.create_user(login='v4a@kaupamex.mx', password='x')
    draft = SaleOrder.objects.create(partner=user, state=SaleOrder.STATE_DRAFT)
    add_item_to_draft(draft, product_v4, quantity=1)
    order = confirm_draft_order(draft, address_data=dict(ADDR))
    return order


class TestReviewAnchorsToCanonical:
    def test_review_carries_sale_order_fk(self, confirmed_order, product_v4):
        review = Review.objects.create(
            user=confirmed_order.partner, product=product_v4,
            sale_order=confirmed_order,
            rating=5, title='Excelente', body='x',
            status=Review.STATUS_PENDING,
        )
        assert review.sale_order_id == confirmed_order.pk
        assert list(confirmed_order.reviews.all()) == [review]


class TestShipmentGuideAnchorsToCanonical:
    def test_guide_carries_sale_order_fk(self, confirmed_order):
        courier = Courier.objects.create(name='DHL V4a', code='DHL4A',
                                         is_active=True)
        guide = ShipmentGuide.objects.create(
            sale_order=confirmed_order, courier=courier,
            tracking_number='V4A-TRK-001',
        )
        assert guide.sale_order_id == confirmed_order.pk
        assert confirmed_order.shipment_guide.pk == guide.pk
