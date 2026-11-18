"""``ir.exports`` e ``ir.exports.line`` con la forma de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_exports.py:7-23``: los atributos de
clase de las dos clases, y ``export_fields`` como ``One2many(copy=True)``,
así que duplicar una exportación duplica sus líneas. Diseño en
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
ir-exports-one2many.md``.
"""
import pytest
from django.apps import apps

pytestmark = pytest.mark.django_db

IrExports = apps.get_model('base', 'IrExports')
IrExportsLine = apps.get_model('base', 'IrExportsLine')


@pytest.mark.parametrize('model, expected', [
    (IrExports, ('ir.exports', 'Exports', 'name, id')),
    (IrExportsLine, ('ir.exports.line', 'Exports Line', 'id')),
])
def test_the_class_attributes_are_the_source_ones(model, expected):
    assert (model._name, model._description, model._order) == expected


def _export_with_lines():
    export = IrExports.objects.create(name='Pedidos', resource='sale.Order')
    for name in ('name', 'amount_total'):
        IrExportsLine.objects.create(name=name, export_id=export)
    return export


def test_copying_an_export_copies_its_lines():
    export = _export_with_lines()
    duplicate = export.copy()
    lines = list(duplicate.export_fields.order_by('id')
                 .values_list('name', flat=True))
    assert lines == ['name', 'amount_total']
    assert not set(duplicate.export_fields.values_list('pk', flat=True)) & \
        set(export.export_fields.values_list('pk', flat=True))


def test_the_original_keeps_its_lines():
    export = _export_with_lines()
    export.copy()
    assert export.export_fields.count() == 2
