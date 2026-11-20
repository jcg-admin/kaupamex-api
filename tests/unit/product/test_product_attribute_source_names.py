"""``attribute_id`` y ``value_ids`` con los nombres de la fuente.

≙ ``odoo19c: addons/product/models/product_attribute_value.py:12-14`` y
``product_template_attribute_line.py:12-16``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-attribute-source-names.md``.

*Métrica:* las cabeceras, el nombre y la columna de los campos que nombran,
y el nombre que muestra una línea.
*Ciega a:* las cabeceras de categoría, tarifa y documento, que el diseño
declara con su sucesor.
"""
import pytest

from addons.product.models import (
    ProductAttribute, ProductAttributeValue, ProductTemplate,
    ProductTemplateAttributeLine)

pytestmark = pytest.mark.django_db


def test_the_attribute_value_header_is_the_reference():
    attrs = ProductAttributeValue.__dict__
    assert attrs['_name'] == 'product.attribute.value'
    assert attrs['_order'] == 'attribute_id, sequence, id'
    assert attrs['_description'] == 'Attribute Value'


def test_the_attribute_line_header_is_the_reference():
    attrs = ProductTemplateAttributeLine.__dict__
    assert attrs['_name'] == 'product.template.attribute.line'
    assert attrs['_rec_name'] == 'attribute_id'
    assert attrs['_rec_names_search'] == ['attribute_id', 'value_ids']
    assert attrs['_description'] == 'Product Template Attribute Line'
    assert attrs['_order'] == 'sequence, attribute_id, id'


@pytest.mark.parametrize('model', [
    ProductAttributeValue, ProductTemplateAttributeLine])
def test_attribute_id_keeps_the_source_name_and_column(model):
    assert model._meta.get_field('attribute_id').column == 'attribute_id'


def test_the_line_values_take_the_source_name():
    assert ProductTemplateAttributeLine._meta.get_field(
        'value_ids').many_to_many


def test_a_line_carries_its_attribute_and_values():
    color = ProductAttribute.objects.create(name='Color')
    red = ProductAttributeValue.objects.create(attribute_id=color, name='Rojo')
    template = ProductTemplate.objects.create(name='Playera')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=template, attribute_id=color)
    line.value_ids.set([red])
    assert line.attribute_id == color
    assert list(line.value_ids.all()) == [red]
    assert red.display_name == 'Color: Rojo'
