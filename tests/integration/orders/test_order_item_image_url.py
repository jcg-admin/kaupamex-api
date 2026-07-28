"""
H-13: OrderItemSerializer debe exponer image_url.

El detalle del pedido no mostraba imágenes porque el serializer no exponía
ningún campo de imagen (item.image_url llegaba undefined al UI). Este guard
verifica que el campo existe y que resuelve a None cuando el item no tiene
producto asociado (FK nullable, SET_NULL si el producto se eliminó).
"""
import pytest

from addons.orders.serializers import OrderItemSerializer
from addons.orders.models import Order, OrderItem
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration


def test_order_item_serializer_exposes_image_url_field():
    assert 'image_url' in OrderItemSerializer().fields


def test_image_url_is_none_when_item_has_no_product(db):
    order = make_order(order_number='PY-IMG00001', status='DELIVERED')
    item = OrderItem.objects.create(
        order=order, product=None, product_name='Pieza histórica',
        sku='SKU-X', unit_price='100.00', quantity=1, subtotal='100.00',
    )
    data = OrderItemSerializer(item).data
    assert data['image_url'] is None
