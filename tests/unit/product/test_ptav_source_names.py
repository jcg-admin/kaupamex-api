"""``product.template.attribute.value``: enlaces con el nombre de la fuente.

≙ ``odoo19c: addons/product/models/product_template_attribute_value.py:27-33``
y la inversa ``product_template_value_ids`` de
``odoo19c: addons/product/models/product_template_attribute_line.py:39-41``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
ptav-source-names.md``.

*Métrica:* nombre y columna de los dos enlaces, la inversa en la línea, el
``related`` de ``name`` y la unicidad por línea y valor.
*Ciega a:* la política de borrado del valor, que el diseño declara divergente
con su sucesor.
"""
import pytest
from django.db import IntegrityError, transaction

from addons.product.models import (
    ProductAttribute, ProductAttributeValue, ProductTemplate,
    ProductTemplateAttributeLine, ProductTemplateAttributeValue)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name', ['attribute_line_id',
                                  'product_attribute_value_id'])
def test_the_link_keeps_the_source_name_and_column(name):
    field = ProductTemplateAttributeValue._meta.get_field(name)
    assert field.column == name


@pytest.fixture
def ptav():
    attribute = ProductAttribute.objects.create(name='Color ptav')
    red = ProductAttributeValue.objects.create(attribute_id=attribute,
                                               name='Rojo ptav')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Camisa ptav'),
        attribute_id=attribute)
    return ProductTemplateAttributeValue.objects.create(
        attribute_line_id=line, product_attribute_value_id=red)


def test_the_line_lists_its_values_by_the_source_inverse(ptav):
    assert list(ptav.attribute_line_id.product_template_value_ids) == [
        ptav]


def test_the_name_is_read_from_the_attribute_value(ptav):
    assert ptav.name == 'Rojo ptav'


def test_a_line_cannot_offer_the_same_value_twice(ptav):
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductTemplateAttributeValue.objects.create(
            attribute_line_id=ptav.attribute_line_id,
            product_attribute_value_id=ptav.product_attribute_value_id)
