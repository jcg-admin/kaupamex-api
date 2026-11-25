"""``ir.exports`` e ``ir.exports.line`` con la forma de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_exports.py:7-23``: los atributos de
clase de las dos clases, y ``export_fields`` como ``One2many(copy=True)``,
así que duplicar una exportación duplica sus líneas. Diseño en
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
ir-exports-one2many.md``.
"""
import pytest
from django.apps import apps

from orm.environments import sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

IrExports = apps.get_model('base', 'IrExports')
IrExportsLine = apps.get_model('base', 'IrExportsLine')


@pytest.mark.parametrize('model, expected', [
    (IrExports, ('ir.exports', 'Exports', 'name, id')),
    (IrExportsLine, ('ir.exports.line', 'Exports Line', 'id')),
])
def test_the_class_attributes_are_the_source_ones(model, expected):
    assert (model._name, model._description, model._order) == expected


@pytest.mark.parametrize('model', [IrExports, IrExportsLine])
def test_both_models_are_basemodel(model):
    """≙ ``class IrExports(models.Model)`` (``odoo19c: ir_exports.py:7,17``):
    en la fuente todo modelo con ``_name`` es ``BaseModel``. El trinquete de
    ``test_basemodel_reach`` mide por app, y ``base`` aún tiene otros."""
    assert issubclass(model, BaseModel)


def _export_with_lines():
    export = IrExports.objects.create(name='Pedidos', resource='sale.Order')
    for name in ('name', 'amount_total'):
        IrExportsLine.objects.create(name=name, export_id=export)
    return export


# Los dos modelos son ``BaseModel``: su ACL rige y la fuente prueba como
# superusuario; ``export_fields`` es un recordset, ordenado por ``_order``.
def test_copying_an_export_copies_its_lines():
    with sudo():
        export = _export_with_lines()
        duplicate = export.copy()
        assert duplicate.export_fields.mapped('name') == [
            'name', 'amount_total']
        assert not set(duplicate.export_fields.ids) & set(
            export.export_fields.ids)


def test_the_original_keeps_its_lines():
    with sudo():
        export = _export_with_lines()
        export.copy()
        assert len(export.export_fields) == 2
