"""``product.template.attribute.value`` completo (etapa 4 del cluster).

≙ ``odoo19c: addons/product/models/product_template_attribute_value.py:
10-198`` y ``product_product.py:744-781`` (``_unlink_or_archive``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
ptav-complete.md``.

*Métrica:* campos, guardas de ``create``/``write``, borrado o archivo, y los
ayudantes de combinación, sobre registros reales.
*Ciega a:* ``exclude_for`` y la regeneración de variantes, que son de las
etapas 3 y 5.
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
from exceptions import UserError, ValidationError
from orm.commands import Command
from orm.environments import env

pytestmark = pytest.mark.django_db

PTAV = 'product.template.attribute.value'


def _attribute(name, create_variant='always', values=('A', 'B')):
    attribute = ProductAttribute.objects.create(
        name=name, create_variant=create_variant)
    return attribute, [ProductAttributeValue.objects.create(
        attribute_id=attribute, name=f'{name} {value}') for value in values]


def _line(template, attribute, values):
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=template, attribute_id=attribute)
    line.write({'value_ids': [Command.set([value.id for value in values])]})
    ptavs = [ProductTemplateAttributeValue.objects.get(
        attribute_line_id=line, product_attribute_value_id=value)
        for value in values]
    return line, ptavs


@pytest.fixture
def template():
    return ProductTemplate.objects.create(name='Camisa PTAV')


def test_the_stored_relations_follow_the_line(template):
    attribute, values = _attribute('Talla PTAV')
    line, (ptav, _other) = _line(template, attribute, values)
    ptav = ProductTemplateAttributeValue.objects.get(pk=ptav.pk)
    assert ptav.product_tmpl_id == template
    assert ptav.attribute_id == attribute
    assert ptav.ptav_active is True
    assert 1 <= ptav.color <= 11


def test_a_value_outside_the_line_is_refused(template):
    attribute, (first, second) = _attribute('Color PTAV')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=template, attribute_id=attribute)
    line.write({'value_ids': [Command.set([first.id])]})
    # Por ``create`` del ORM, que valida las ``@api.constrains``.
    with pytest.raises(ValidationError):
        env()[PTAV].create([{
            'attribute_line_id': line.id,
            'product_attribute_value_id': second.id,
        }])


def test_write_refuses_to_change_the_value_or_the_variants(template):
    attribute, values = _attribute('Material PTAV')
    _line_record, (ptav, other) = _line(template, attribute, values)
    with pytest.raises(UserError):
        ptav.write({
            'product_attribute_value_id': other.product_attribute_value_id.id,
        })
    with pytest.raises(UserError):
        ptav.write({'ptav_product_variant_ids': [Command.clear()]})
    with pytest.raises(UserError):
        env()[PTAV].create([{
            'attribute_line_id': ptav.attribute_line_id.id,
            'product_attribute_value_id': ptav.product_attribute_value_id.id,
            'ptav_product_variant_ids': [Command.clear()],
        }])


def test_the_display_name_carries_the_attribute(template):
    attribute, values = _attribute('Corte PTAV')
    _line_record, (ptav, _other) = _line(template, attribute, values)
    assert ptav.display_name == f'Corte PTAV: {ptav.name}'


def test_the_combination_name_skips_single_value_and_no_variant_lines(
        template):
    multi, multi_values = _attribute('Talla combo')
    single, single_values = _attribute('Marca combo', values=('Unica',))
    never, never_values = _attribute('Nota combo', create_variant='no_variant')
    _l1, (big, _small) = _line(template, multi, multi_values)
    _l2, (brand,) = _line(template, single, single_values)
    _l3, (note, _other) = _line(template, never, never_values)
    combination = big | brand | note
    assert combination._get_combination_name() == big.name
    assert combination._ids2str() == ','.join(
        str(i) for i in sorted(combination.ids))


def test_unlink_deletes_a_free_value_and_archives_a_used_one(template):
    attribute, values = _attribute('Forma PTAV')
    _line_record, (free, used) = _line(template, attribute, values)
    free.unlink()
    assert not ProductTemplateAttributeValue.objects.filter(
        pk=free.pk).exists()
    # Un valor que una variante archivada retiene no se puede borrar.
    variant = ProductProduct.objects.create(
        product_tmpl_id=template, active=False)
    variant.write({
        'product_template_attribute_value_ids': [Command.link(used.id)],
    })
    used.unlink()
    used = ProductTemplateAttributeValue.objects.get(pk=used.pk)
    assert used.ptav_active is False


def test_unlink_or_archive_archives_what_it_cannot_delete(template):
    attribute, values = _attribute('Uso PTAV')
    _line_record, (ptav, _other) = _line(template, attribute, values)
    kept = ProductProduct.objects.create(product_tmpl_id=template)
    kept.write({
        'product_template_attribute_value_ids': [Command.link(ptav.id)],
    })
    ProductTemplateAttributeValue.objects.filter(pk=ptav.pk).update(
        ptav_active=True)
    gone = ProductProduct.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name='Libre PTAV'))
    (kept | gone)._unlink_or_archive()
    assert not ProductProduct.objects.filter(pk=gone.pk).exists()
