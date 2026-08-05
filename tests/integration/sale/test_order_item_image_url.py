"""
H-13: OrderItemSerializer debe exponer image_url.

El detalle del pedido no mostraba imágenes porque el serializer no exponía
ningún campo de imagen (item.image_url llegaba undefined al UI). Este guard
verifica que el campo existe.

``test_image_url_is_none_when_item_has_no_product`` se retiró: probaba
``SaleOrderLine.objects.create(product=None, ...)`` asumiendo un FK nullable
con ``SET_NULL`` — cita textual del docstring original: *"FK nullable,
SET_NULL si el producto se eliminó"*. El campo canónico
(``src/addons/sale/models/sale_order_line.py:28-31``) es
``on_delete=models.PROTECT`` **sin** ``null=True``: una línea sin producto es
un estado que la BD ya no permite crear. La rama ``obj.product_id is None`` de
``OrderItemSerializer.get_image_url`` (``src/addons/sale/serializers.py:110-111``)
queda como código muerto — no hay forma de alcanzarla desde una fila real —,
lo cual es un hallazgo aparte, no algo que este test pueda seguir ejerciendo.
"""
from addons.sale.controllers.serializers import OrderItemSerializer
import pytest

pytestmark = pytest.mark.integration


def test_order_item_serializer_exposes_image_url_field():
    assert 'image_url' in OrderItemSerializer().fields
