"""Ordenar por un campo heredado por ``_inherits``.

≙ ``odoo19c: odoo/orm/models.py:2910-2934`` (``_field_to_sql``): el campo
heredado es un ``related`` no almacenado y se ordena por el join de la
clave de delegación. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/order-by-inherited-field.md``.

*Métrica:* el camino que ``order_to_django`` da para ``name`` en
``product.product`` y el orden real de dos variantes.
*Ciega a:* ``_inherits`` de varios niveles, que el puerto no propaga.
"""
import pytest

from addons.product.models import ProductProduct, ProductTemplate
from orm.models import order_to_django

pytestmark = pytest.mark.django_db


def test_an_inherited_field_orders_through_the_delegation_key():
    [term] = order_to_django(ProductProduct, 'name')
    assert term.expression.name == 'product_tmpl_id__name'


def test_variants_follow_the_name_of_their_templates():
    zeta = ProductProduct.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Zeta oibf'))
    alpha = ProductProduct.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Alfa oibf'))
    rows = ProductProduct.objects.filter(pk__in=[zeta.pk, alpha.pk]).order_by(
        *order_to_django(ProductProduct, 'name'))
    assert [row.pk for row in rows] == [alpha.pk, zeta.pk]
