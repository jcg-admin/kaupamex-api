"""``CategoryTreeSerializer`` sobre el One2many ``child_id``.

``product.category`` es ``BaseModel``: ``child_id`` (el inverso de
``parent_id``) es un recordset, como en la fuente, y el serializador lo
leía con ``all().order_by('name')``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-reverse-queryset.md``.

*Métrica:* el árbol serializado de una categoría con dos hijas.
*Ciega a:* el resto de la API de la tienda.
"""
import pytest

from addons.product.models import ProductCategory
from addons.website_sale.controllers.serializers import CategoryTreeSerializer
from orm.environments import sudo

pytestmark = pytest.mark.django_db


def test_the_children_come_out_sorted_by_name():
    with sudo():
        root = ProductCategory.objects.create(name='CTS Raíz')
        ProductCategory.objects.create(name='CTS Zeta', parent_id=root)
        ProductCategory.objects.create(name='CTS Alfa', parent_id=root)
        data = CategoryTreeSerializer(
            ProductCategory.objects.get(pk=root.pk)).data
    assert [c['name'] for c in data['children']] == ['CTS Alfa', 'CTS Zeta']
