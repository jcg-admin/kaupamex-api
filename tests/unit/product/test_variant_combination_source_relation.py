"""Combinación de la variante: la relación de la fuente.

≙ ``odoo19c: addons/product/models/product_product.py:49`` y
``odoo19c: addons/product/models/product_template_attribute_value.py:55-57``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
variant-combination-source-relation.md``.

*Métrica:* columnas de ``product_variant_combination`` y la inversa
``ptav_product_variant_ids``.
*Ciega a:* el ``ondelete='restrict'`` de ``column2``, que es otra unidad.
"""
import pytest

from addons.product.models import (
    ProductAttribute, ProductAttributeValue, ProductProduct, ProductTemplate,
    ProductTemplateAttributeLine, ProductTemplateAttributeValue)
from orm.commands import Command

pytestmark = pytest.mark.django_db


def test_the_combination_table_and_columns_are_the_source_ones():
    through = ProductProduct._meta.get_field(
        'product_template_attribute_value_ids').remote_field.through
    columns = {f.column for f in through._meta.local_fields} - {'id'}
    assert through._meta.db_table == 'product_variant_combination'
    assert columns == {'product_product_id',
                       'product_template_attribute_value_id'}


def test_a_value_reaches_the_variants_that_use_it():
    attribute = ProductAttribute.objects.create(name='Color vcsr')
    red = ProductAttributeValue.objects.create(attribute_id=attribute,
                                               name='Rojo vcsr')
    template = ProductTemplate.objects.create(name='Gorra vcsr')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=template, attribute_id=attribute)
    ptav = ProductTemplateAttributeValue.objects.create(
        attribute_line_id=line, product_attribute_value_id=red)
    variant = ProductProduct.objects.create(product_tmpl_id=template)
    variant.write({
        'product_template_attribute_value_ids': [Command.link(ptav.id)],
    })
    assert list(ptav.ptav_product_variant_ids) == [variant]
