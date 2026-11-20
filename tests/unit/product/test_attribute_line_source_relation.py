"""Líneas de atributo: las inversas y la tabla de la fuente.

≙ ``odoo19c: addons/product/models/product_template_attribute_line.py:32-36``,
``product_attribute_value.py:29-33`` y ``product_attribute.py:59-62``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
attribute-line-source-relation.md``.

*Métrica:* tabla y columnas de la intermedia de ``value_ids`` y las dos
inversas.
*Ciega a:* la guarda de borrado del valor, que es la mitad (b) del sucesor.
"""
import pytest

from addons.product.models import (
    ProductAttribute, ProductAttributeValue, ProductTemplate,
    ProductTemplateAttributeLine)
from orm.commands import Command

pytestmark = pytest.mark.django_db


def test_the_relation_table_and_columns_are_the_source_ones():
    through = ProductTemplateAttributeLine._meta.get_field(
        'value_ids').remote_field.through
    columns = {f.column for f in through._meta.local_fields} - {'id'}
    assert through._meta.db_table == (
        'product_attribute_value_product_template_attribute_line_rel')
    assert columns == {'product_template_attribute_line_id',
                       'product_attribute_value_id'}


def test_the_attribute_and_the_value_reach_their_lines():
    attribute = ProductAttribute.objects.create(name='Talla alsr')
    small = ProductAttributeValue.objects.create(attribute_id=attribute,
                                                 name='Chica alsr')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Polo alsr'),
        attribute_id=attribute)
    line.write({'value_ids': [Command.set([record.id for record in [small]])]})
    assert list(attribute.attribute_line_ids.all()) == [line]
    assert list(small.pav_attribute_line_ids) == [line]
