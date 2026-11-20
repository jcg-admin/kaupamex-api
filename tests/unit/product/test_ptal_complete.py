"""Porte completo de ``product.template.attribute.line`` (etapa 2).

≙ ``odoo19c: addons/product/models/product_template_attribute_line.py``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
ptal-complete.md``.

*Métrica:* los valores de plantilla y las variantes que deja cada operación
del ORM sobre la línea, y los rechazos de las restricciones.
*Ciega a:* ``action_open_attribute_values``, que depende de las vistas de
``product`` (sucesor ``product-views-0122``).
"""
import pytest

from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductTemplateAttributeValue,
)
from exceptions import UserError, ValidationError
from orm.commands import Command
from orm.environments import env

pytestmark = pytest.mark.django_db

TEMPLATE = 'product.template'
LINE = 'product.template.attribute.line'


def _attribute(name, create_variant='always', values=('A', 'B')):
    attribute = ProductAttribute.objects.create(
        name=name, create_variant=create_variant)
    return attribute, [ProductAttributeValue.objects.create(
        attribute_id=attribute, name=f'{name} {value}') for value in values]


def _template(name):
    [template] = env()[TEMPLATE].create([{'name': name}])
    return template


def _line(template, attribute, values):
    [line] = env()[LINE].create([{
        'product_tmpl_id': template.id,
        'attribute_id': attribute.id,
        'value_ids': [Command.set([value.id for value in values])],
    }])
    return line


def _active_values(line):
    return set(ProductTemplateAttributeValue.objects.filter(
        attribute_line_id=line.id, ptav_active=True,
    ).values_list('product_attribute_value_id', flat=True))


def test_creating_a_line_creates_its_values_and_variants():
    template = _template('PTAL alta')
    attribute, values = _attribute('PTAL Color')
    line = _line(template, attribute, values)
    assert _active_values(line) == {value.id for value in values}
    template.invalidate_recordset()
    assert len(template.product_variant_ids) == 2


def test_the_value_count_follows_the_values():
    template = _template('PTAL conteo')
    attribute, values = _attribute('PTAL Talla', values=('S', 'M', 'L'))
    line = _line(template, attribute, values)
    assert line.value_count == 3


def test_removing_a_value_removes_its_template_value():
    template = _template('PTAL quitar')
    attribute, values = _attribute('PTAL Tela')
    line = _line(template, attribute, values)
    line.write({'value_ids': [Command.set([values[0].id])]})
    assert _active_values(line) == {values[0].id}


def test_an_active_line_needs_a_value():
    template = _template('PTAL vacía')
    attribute, _values = _attribute('PTAL Vacío')
    with pytest.raises(ValidationError):
        _line(template, attribute, [])


def test_a_value_of_another_attribute_is_rejected():
    template = _template('PTAL ajeno')
    attribute, _values = _attribute('PTAL Propio')
    _other, foreign = _attribute('PTAL Ajeno')
    with pytest.raises(ValidationError):
        _line(template, attribute, foreign)


def test_the_line_cannot_move_to_another_template():
    template = _template('PTAL origen')
    target = _template('PTAL destino')
    attribute, values = _attribute('PTAL Mover')
    line = _line(template, attribute, values)
    with pytest.raises(UserError):
        line.write({'product_tmpl_id': target.id})


def test_the_line_cannot_change_its_attribute():
    template = _template('PTAL atributo')
    attribute, values = _attribute('PTAL Fijo')
    other, _values = _attribute('PTAL Otro')
    line = _line(template, attribute, values)
    with pytest.raises(UserError):
        line.write({'attribute_id': other.id})


def test_archiving_a_line_clears_its_values():
    template = _template('PTAL archivar')
    attribute, values = _attribute('PTAL Archivo')
    line = _line(template, attribute, values)
    line.write({'active': False})
    line.invalidate_recordset()
    assert not line.value_ids
    assert not _active_values(line)


def test_creating_reactivates_the_archived_line():
    template = _template('PTAL reactivar')
    attribute, values = _attribute('PTAL Reactivo')
    line = _line(template, attribute, values)
    line.write({'active': False})
    again = _line(template, attribute, values[:1])
    assert again.id == line.id
    assert again.active
    assert _active_values(again) == {values[0].id}


def test_unlinking_a_line_regenerates_the_variants():
    template = _template('PTAL borrar')
    attribute, values = _attribute('PTAL Borrado')
    line = _line(template, attribute, values)
    line.unlink()
    template.invalidate_recordset()
    assert len(template.product_variant_ids) == 1
    variant = template.product_variant_ids
    assert not variant.product_template_attribute_value_ids


def test_a_no_variant_attribute_brings_all_its_values():
    attribute, values = _attribute('PTAL Grabado', create_variant='no_variant')
    line = env()[LINE].new({'attribute_id': attribute.id})
    line._onchange_attribute_id()
    assert set(line.value_ids.ids) == {value.id for value in values}
