"""Tests — V4a unificación orders→sale (``analisis-unificar-orders-sale``).

Post-venta y logística anclan al canónico: ``rating.Review`` (prueba de
compra UC-REV-02) y ``delivery.ShipmentGuide`` (el eje de fulfillment,
adaptación de ``stock.picking``) ganan la FK dual ``sale_order``,
propagada desde el enlace del espejo (``Order.sale_order``, V3a).
"""
import uuid
from decimal import Decimal

import pytest

from addons.catalogue.models import Category, Product
from addons.delivery.models import Courier, ShipmentGuide
from addons.rating.models import Review
from addons.sale.models import SaleOrder
from addons.sale.services import add_item_to_draft, confirm_draft_order

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'Test V4a', 'street': 'Calle 2', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '06600',
}


@pytest.fixture
def product_v4(db):
    cat = Category.objects.create(name='Cat V4a', slug='cat-v4a', is_active=True)
    p = Product.objects.create(
        name='Prod V4a', slug='prod-v4a', sku='V4A-001', description='',
        price=Decimal('120.00'), stock=6, is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


@pytest.fixture
def confirmed_pair(product_v4, django_user_model):
    user = django_user_model.objects.create_user(
        email='v4a@test.mx', password='x')
    draft = SaleOrder.objects.create(
        partner=user, state=SaleOrder.STATE_DRAFT)
    add_item_to_draft(draft, product_v4, quantity=1)
    legacy = confirm_draft_order(draft, address_data=dict(ADDR))
    draft.refresh_from_db()
    return draft, legacy


class TestReviewAnchorsToCanonical:
    def test_review_carries_sale_order_fk(self, confirmed_pair, product_v4):
        canonical, legacy = confirmed_pair
        review = Review.objects.create(
            user=legacy.user, product=product_v4, order=legacy,
            sale_order=legacy.sale_order,
            rating=5, title='Excelente', body='x',
            status=Review.STATUS_PENDING,
        )
        assert review.sale_order_id == canonical.pk
        assert list(canonical.reviews.all()) == [review]


class TestShipmentGuideAnchorsToCanonical:
    def test_guide_carries_sale_order_fk(self, confirmed_pair):
        canonical, legacy = confirmed_pair
        courier = Courier.objects.create(name='DHL V4a', code='DHL4A',
                                         is_active=True)
        guide = ShipmentGuide.objects.create(
            order=legacy, sale_order=legacy.sale_order, courier=courier,
            tracking_number='V4A-TRK-001',
        )
        assert guide.sale_order_id == canonical.pk
        assert canonical.shipment_guide.pk == guide.pk
