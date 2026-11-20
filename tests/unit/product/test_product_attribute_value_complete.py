"""``product.attribute.value`` completo, sobre ``BaseModel``.

≙ ``odoo19c: addons/product/models/product_attribute_value.py`` (cabecera
``:12-14``, campos ``:19-58``, métodos ``:62-190``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-attribute-value-complete.md``.

*Métrica:* la base del modelo, sus campos, el ``display_name``, el cómputo
de uso, la guarda de borrado, el archivo en lugar del borrado y la guarda
de cambio de atributo, más el ``cascade`` de PTAV.
*Ciega a:* ``translate=True`` de ``name`` (TASK-GEN-0060) y al asistente
``update.product.attribute.value`` que nombran las dos acciones.
"""
import pytest

from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductProduct,
    ProductTemplate,
    ProductTemplateAttributeLine,
    ProductTemplateAttributeValue,
)
from exceptions import UserError
from orm.models import BaseModel
from orm.commands import Command

pytestmark = pytest.mark.django_db

FIELDS = ('name', 'sequence', 'attribute_id', 'pav_attribute_line_ids',
          'default_extra_price', 'is_custom', 'html_color', 'display_type',
          'color', 'image', 'active', 'is_used_on_products',
          'default_extra_price_changed')


@pytest.fixture
def color():
    return ProductAttribute.objects.create(name='Color')


@pytest.fixture
def red(color):
    return ProductAttributeValue.objects.create(attribute_id=color,
                                                name='Rojo')


def _used(value, template_name='Playera'):
    """Una plantilla activa cuya línea usa ``value``, con su PTAV."""
    template = ProductTemplate.objects.create(name=template_name)
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=template, attribute_id=value.attribute_id)
    line.write({'value_ids': [Command.set([record.id for record in [value]])]})
    ptav = ProductTemplateAttributeValue.objects.create(
        attribute_line_id=line, product_attribute_value_id=value)
    return template, ptav


def test_the_value_is_a_base_model_with_the_source_fields():
    assert issubclass(ProductAttributeValue, BaseModel)
    assert set(FIELDS) <= set(ProductAttributeValue._fields)
    assert vars(ProductAttributeValue)['_order'] == (
        'attribute_id, sequence, id')


def test_the_color_default_is_in_the_source_range(red):
    assert 1 <= red.color <= 11


def test_the_display_name_names_the_attribute_unless_told_not_to(
        superuser_env, red):
    value = superuser_env['product.attribute.value'].browse(red.pk)
    assert value.display_name == 'Color: Rojo'
    assert value.with_context(show_attribute=False).display_name == 'Rojo'


def test_a_value_on_an_active_template_line_is_used(superuser_env, red):
    value = superuser_env['product.attribute.value'].browse(red.pk)
    assert not value.is_used_on_products
    _used(red)
    value.invalidate_recordset()
    assert value.is_used_on_products


def test_a_used_value_is_not_deleted(superuser_env, red):
    _used(red)
    value = superuser_env['product.attribute.value'].browse(red.pk)
    with pytest.raises(UserError, match='Playera'):
        value.unlink()
    assert value.exists()


def test_a_value_used_only_by_archived_variants_is_archived(
        superuser_env, red):
    template, ptav = _used(red)
    template.active = False
    template.save()
    variant = ProductProduct.objects.create(product_tmpl_id=template,
                                            active=False)
    variant.write({
        'product_template_attribute_value_ids': [Command.set([ptav.id])],
    })
    value = superuser_env['product.attribute.value'].browse(red.pk)
    value.unlink()
    assert value.exists()
    assert not value.active


def test_an_unused_value_is_deleted_with_its_template_values(
        superuser_env, red):
    template = ProductTemplate.objects.create(name='Gorra')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=template, attribute_id=red.attribute_id)
    ptav = ProductTemplateAttributeValue.objects.create(
        attribute_line_id=line, product_attribute_value_id=red)
    superuser_env['product.attribute.value'].browse(red.pk).unlink()
    assert not ProductAttributeValue.objects.filter(pk=red.pk).exists()
    assert not ProductTemplateAttributeValue.objects.filter(
        pk=ptav.pk).exists()


def test_the_attribute_of_a_used_value_cannot_change(superuser_env, red):
    _used(red)
    size = ProductAttribute.objects.create(name='Talla')
    value = superuser_env['product.attribute.value'].browse(red.pk)
    with pytest.raises(UserError, match='change the attribute'):
        value.write({'attribute_id': size.pk})


def test_the_extra_price_changed_flag_compares_with_the_template_values(
        superuser_env, red):
    _, ptav = _used(red)
    value = superuser_env['product.attribute.value'].browse(red.pk)
    assert not value.default_extra_price_changed
    ptav.price_extra = 5
    ptav.save()
    value.invalidate_recordset()
    assert value.default_extra_price_changed


def test_the_actions_return_the_source_wizard(superuser_env, red):
    value = superuser_env['product.attribute.value'].browse(red.pk)
    action = value.action_update_prices()
    assert action['res_model'] == 'update.product.attribute.value'
    assert action['context']['default_mode'] == 'update_extra_price'
    assert value.action_add_to_products()['context']['default_mode'] == 'add'
