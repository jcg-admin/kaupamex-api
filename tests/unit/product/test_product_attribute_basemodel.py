"""``product.attribute`` como ``BaseModel``, completo.

≙ ``odoo19c: addons/product/models/product_attribute.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-attribute-basemodel.md``.

*Métrica:* la restricción, los productos y su conteo que el atributo deriva
de sus líneas, y los rechazos de ``write``, el borrado y el archivado.
*Ciega a:* la vista que abre
``action_open_product_template_attribute_lines``: se comprueba su
diccionario, no el cliente web.
"""
import pytest
from django.db import IntegrityError, transaction

from addons.product.models import ProductAttribute, ProductAttributeValue
from exceptions import UserError
from orm.commands import Command
from orm.environments import env
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

ATTRIBUTE = 'product.attribute'


def _attribute(**vals):
    values = dict({'name': 'PA Color'}, **vals)
    [attribute] = env()[ATTRIBUTE].create([values])
    return attribute


def _used(attribute, name='PA Producto'):
    value = ProductAttributeValue.objects.create(
        attribute_id=attribute, name=f'{attribute.name} valor')
    [template] = env()['product.template'].create([{'name': name}])
    env()['product.template.attribute.line'].create([{
        'product_tmpl_id': template.id,
        'attribute_id': attribute.id,
        'value_ids': [Command.set([value.id])],
    }])
    attribute.invalidate_recordset()
    return template


def test_the_attribute_is_a_basemodel_with_the_source_defaults():
    attribute = _attribute()
    assert issubclass(ProductAttribute, BaseModel)
    assert attribute.sequence == 20
    assert attribute.active


def test_multi_checkbox_cannot_create_variants():
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductAttribute.objects.create(
            name='PA Multi', display_type='multi', create_variant='always')


def test_the_products_and_their_count_follow_the_lines():
    attribute = _attribute()
    template = _used(attribute)
    assert template.id in attribute.product_tmpl_ids.ids
    assert attribute.number_related_products == 1


def test_a_used_attribute_keeps_its_variant_mode():
    attribute = _attribute()
    _used(attribute)
    with pytest.raises(UserError):
        attribute.write({'create_variant': 'no_variant'})


def test_a_used_attribute_cannot_be_deleted():
    attribute = _attribute()
    _used(attribute)
    with pytest.raises(UserError):
        attribute.unlink()


def test_a_used_attribute_cannot_be_archived():
    attribute = _attribute()
    _used(attribute)
    with pytest.raises(UserError):
        attribute.action_archive()


def test_choosing_multi_on_an_unused_attribute_stops_variants():
    attribute = env()[ATTRIBUTE].new({'name': 'PA Nuevo',
                                      'display_type': 'multi'})
    attribute._onchange_display_type()
    assert attribute.create_variant == 'no_variant'


def test_the_tooling_skips_no_variant_attributes():
    always = _attribute(name='PA Siempre')
    never = _attribute(name='PA Nunca', create_variant='no_variant')
    both = always | never
    assert both._without_no_variant_attributes() == always


def test_the_action_opens_the_lines_of_active_products():
    attribute = _attribute()
    action = attribute.action_open_product_template_attribute_lines()
    assert action['res_model'] == 'product.template.attribute.line'
    assert ('attribute_id', '=', attribute.id) in action['domain']
