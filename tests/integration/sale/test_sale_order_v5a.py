"""Tests — V5a unificación orders→sale (``analisis-unificar-orders-sale``).

El sub-estado de preparación (Odoo ``stock.picking`` + ``sale.order.
delivery_status``) YA existe; V5a lo **ancla** al canónico con la FK
``StockPicking.sale_order`` (Odoo ``stock.picking.sale_id``) para que
``IN_PREPARATION`` (albarán ``assigned`` sin guía de transportista) sea
proyectable sin depender del enum monolítico ``Order.status`` (H-SALE-09).
"""
import uuid
from decimal import Decimal

import pytest

from addons.sale.models import SaleOrder
from addons.sale_stock.models import SaleOrderDelivery
from addons.stock.models import StockPicking

pytestmark = pytest.mark.django_db


@pytest.fixture
def sale_order(db):
    return SaleOrder.objects.create(
        state=SaleOrder.STATE_SALE, cart_token=uuid.uuid4())


class TestPickingAnchorsToCanonical:
    def test_picking_carries_sale_order_fk(self, sale_order):
        picking = StockPicking.objects.create(
            sale_order=sale_order, state=StockPicking.STATE_CONFIRMED)
        picking.action_assign()
        picking.refresh_from_db()
        assert picking.sale_order_id == sale_order.pk
        assert picking.state == StockPicking.STATE_ASSIGNED
        assert list(sale_order.pickings.all()) == [picking]

    def test_sale_order_fk_is_nullable_for_legacy_rows(self, db):
        picking = StockPicking.objects.create(state=StockPicking.STATE_DRAFT)
        assert picking.sale_order_id is None


class TestInPreparationIsProjectable:
    """IN_PREPARATION = albarán ``assigned`` (o delivery_status ``started``)
    sin guía de transportista — distinguible de PAID (sin albarán)."""

    def test_assigned_picking_without_guide_marks_in_preparation(self, sale_order):
        # PAID: sin albarán, sin guía.
        assert not sale_order.pickings.exists()
        assert not hasattr(sale_order, 'shipment_guide')
        # Transición a preparación: albarán asignado + delivery_status started.
        picking = StockPicking.objects.create(
            sale_order=sale_order, state=StockPicking.STATE_CONFIRMED)
        picking.action_assign()
        delivery = SaleOrderDelivery.objects.create(
            order=sale_order, delivery_status=SaleOrderDelivery.STATUS_STARTED)
        assert sale_order.pickings.filter(
            state=StockPicking.STATE_ASSIGNED).exists()
        assert delivery.delivery_status == SaleOrderDelivery.STATUS_STARTED
        assert not hasattr(sale_order, 'shipment_guide')
