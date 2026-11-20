"""Generación de variantes y exclusiones (etapas 3 y 5 del cluster).

≙ ``odoo19c: addons/product/models/product_template.py:567-596,770-1128`` y
``product_template_attribute_exclusion.py:6-47``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-template-variant-generation.md``.

*Métrica:* las variantes activas que quedan por combinación, tras crear
plantillas, exclusiones y archivar.
*Ciega a:* la creación de los valores de plantilla desde la línea
(``_update_product_template_attribute_values``), que es la etapa de la
línea: aquí los valores se crean a mano.
"""
import pytest

from addons.base.models import SystemParameter
from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductTemplate,
    ProductTemplateAttributeLine,
    ProductTemplateAttributeValue,
)
from exceptions import UserError
from orm.commands import Command
from orm.environments import env

pytestmark = pytest.mark.django_db

TEMPLATE = 'product.template'
EXCLUSION = 'product.template.attribute.exclusion'


def _attribute(name, create_variant='always', values=('A', 'B')):
    attribute = ProductAttribute.objects.create(
        name=name, create_variant=create_variant)
    return attribute, [ProductAttributeValue.objects.create(
        attribute_id=attribute, name=f'{name} {value}') for value in values]


def _line(template, attribute, values):
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=template, attribute_id=attribute)
    line.write({'value_ids': [Command.set([value.id for value in values])]})
    return [ProductTemplateAttributeValue.objects.create(
        attribute_line_id=line, product_attribute_value_id=value)
        for value in values]


def _combinations(template):
    template.invalidate_recordset()
    return {frozenset(variant.product_template_attribute_value_ids.ids)
            for variant in template.product_variant_ids}


def test_creating_a_template_creates_its_variant():
    [template] = env()[TEMPLATE].create([{'name': 'Sin atributos VG'}])
    assert len(template.product_variant_ids) == 1


def test_the_context_can_skip_the_variants():
    [template] = env()[TEMPLATE].with_context(
        create_product_product=False).create([{'name': 'Sin variantes VG'}])
    assert len(template.product_variant_ids) == 0


def test_the_cartesian_product_of_the_lines_becomes_variants():
    template = ProductTemplate.objects.create(name='Camisa VG')
    size, sizes = _attribute('Talla VG')
    color, colors = _attribute('Color VG')
    size_values = _line(template, size, sizes)
    color_values = _line(template, color, colors)
    template._create_variant_ids()
    assert _combinations(template) == {
        frozenset({s.id, c.id}) for s in size_values for c in color_values}


def test_no_variant_attributes_do_not_multiply_variants():
    template = ProductTemplate.objects.create(name='Taza VG')
    size, sizes = _attribute('Tamaño VG')
    note, notes = _attribute('Grabado VG', create_variant='no_variant')
    size_values = _line(template, size, sizes)
    _line(template, note, notes)
    template._create_variant_ids()
    assert _combinations(template) == {
        frozenset({value.id}) for value in size_values}


def test_an_exclusion_removes_the_combination_it_forbids():
    template = ProductTemplate.objects.create(name='Gorra VG')
    size, sizes = _attribute('Medida VG')
    color, colors = _attribute('Tono VG')
    (small, large) = _line(template, size, sizes)
    (red, blue) = _line(template, color, colors)
    template._create_variant_ids()
    env()[EXCLUSION].create([{
        'product_tmpl_id': template.id,
        'product_template_attribute_value_id': red.id,
        'value_ids': [Command.set([small.id])],
    }])
    assert _combinations(template) == {
        frozenset({small.id, blue.id}),
        frozenset({large.id, red.id}),
        frozenset({large.id, blue.id}),
    }


def test_dynamic_attributes_are_not_generated_in_advance():
    template = ProductTemplate.objects.create(name='Mueble VG')
    finish, finishes = _attribute('Acabado VG', create_variant='dynamic')
    _line(template, finish, finishes)
    template._create_variant_ids()
    assert _combinations(template) == set()


def test_archiving_the_template_archives_its_variants():
    [template] = env()[TEMPLATE].create([{'name': 'Archivo VG'}])
    variant = template.product_variant_ids
    template.write({'active': False})
    variant.invalidate_recordset()
    assert variant.active is False


def test_the_variant_limit_is_enforced():
    template = ProductTemplate.objects.create(name='Límite VG')
    size, sizes = _attribute('Grande VG', values=('A', 'B', 'C'))
    _line(template, size, sizes)
    SystemParameter.set_param('product.dynamic_variant_limit', '2')
    with pytest.raises(UserError):
        template._create_variant_ids()
