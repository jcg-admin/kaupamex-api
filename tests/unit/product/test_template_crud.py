"""Campos de la plantilla leídos de su variante única y CRUD restante.

≙ ``odoo19c: addons/product/models/product_template.py:269-351,436-442,
509-511,567-606``. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/product-template-crud.md``.

*Métrica:* el valor que la plantilla lee y escribe en su variante, la
búsqueda traducida a las variantes, la copia en el alta, ``combo_ids`` al
cambiar de tipo y el gancho ``_update_uom`` al cambiar la unidad.
*Ciega a:* la invalidación de imágenes de la variante, que no las declara
(sucesor ``product-variant-images-0122``).
"""
from decimal import Decimal

import pytest

from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductCombo,
)
from addons.uom.models.uom_uom import Uom
from orm.commands import Command
from orm.environments import env

pytestmark = pytest.mark.django_db

TEMPLATE = 'product.template'
LINE = 'product.template.attribute.line'


def _template(**vals):
    [template] = env()[TEMPLATE].create([dict({'name': 'Plantilla CRUD'},
                                              **vals)])
    return template


def _two_variants(template):
    attribute = ProductAttribute.objects.create(name='Color CRUD')
    values = [ProductAttributeValue.objects.create(
        attribute_id=attribute, name=name) for name in ('Rojo', 'Azul')]
    env()[LINE].create([{
        'product_tmpl_id': template.id,
        'attribute_id': attribute.id,
        'value_ids': [Command.set([value.id for value in values])],
    }])
    template.invalidate_recordset()


def test_the_template_reads_the_single_variant():
    template = _template()
    variant = template.product_variant_ids
    variant.write({'standard_price': Decimal('7.50'), 'volume': 2.0,
                   'weight': 3.0, 'default_code': 'SKU-1',
                   'barcode': '0000001'})
    template.invalidate_recordset()
    assert template.standard_price == Decimal('7.50')
    assert template.volume == 2.0
    assert template.weight == 3.0
    assert template.default_code == 'SKU-1'
    assert template.barcode == '0000001'


def test_writing_the_template_writes_the_single_variant():
    template = _template()
    template.write({'weight': 4.5, 'default_code': 'SKU-2'})
    variant = template.product_variant_ids
    variant.invalidate_recordset()
    assert variant.weight == 4.5
    assert variant.default_code == 'SKU-2'


def test_with_several_variants_the_template_keeps_the_default():
    template = _template()
    _two_variants(template)
    assert len(template.product_variant_ids) == 2
    template.product_variant_ids[0].write({'default_code': 'ONE'})
    template.invalidate_recordset()
    assert not template.default_code


def test_creating_the_template_copies_the_shared_fields_to_its_variant():
    template = _template(default_code='ALTA-1', weight=1.25)
    variant = template.product_variant_ids
    assert variant.default_code == 'ALTA-1'
    assert variant.weight == 1.25


def test_the_barcode_search_goes_through_the_variants():
    template = _template()
    template.product_variant_ids.write({'barcode': '7501234567890'})
    found = env()[TEMPLATE].search([('barcode', '=', '7501234567890')])
    assert found.ids == [template.id]


def test_the_cost_search_goes_through_the_variants():
    template = _template()
    template.product_variant_ids.write({'standard_price': Decimal('123.45')})
    found = env()[TEMPLATE].search([('standard_price', '=', 123.45)])
    assert template.id in found.ids


def test_leaving_the_combo_type_clears_the_combo_choices():
    template = _template(type='combo')
    combo = ProductCombo.objects.create(name='Combo CRUD')
    template.write({'combo_ids': [Command.set([combo.pk])]})
    template.write({'type': 'consu'})
    template.invalidate_recordset()
    assert not template.combo_ids.exists()


def test_changing_the_unit_calls_the_variant_hook(monkeypatch):
    template = _template()
    other = Uom.objects.create(name='Otra unidad CRUD', relative_factor=1.0)
    calls = []
    variant_cls = type(template.product_variant_ids)
    monkeypatch.setattr(
        variant_cls, '_update_uom',
        lambda self, to_uom_id: calls.append((self.ids, to_uom_id)))
    template.write({'uom_id': other.pk})
    assert calls == [(template.product_variant_ids.ids, other.pk)]
