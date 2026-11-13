"""``copy`` y su cadena en todo modelo concreto propio.

≙ ``copy_data``, ``copy_translations`` y ``copy`` en ``BaseModel``
(``odoo19c: odoo/orm/models.py:5406-5545``): allá **todo** modelo los
tiene. Aquí los lleva ``CopyMixin``, y ``orm.model_classes.adopt_copy``
los entrega a quien no los hereda. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
copy-universality.md``.
"""
import pytest
from django.apps import apps

from orm.model_classes import THIRD_PARTY_MODULE_PREFIXES

pytestmark = pytest.mark.django_db

IrExports = apps.get_model('base', 'IrExports')
IrExportsLine = apps.get_model('base', 'IrExportsLine')


def test_a_timestamped_model_duplicates_its_row():
    original = IrExports.objects.create(name='Pedidos',
                                        resource='sale.SaleOrder')
    duplicate = original.copy()
    assert duplicate.pk != original.pk
    assert (duplicate.name, duplicate.resource) == ('Pedidos',
                                                    'sale.SaleOrder')
    assert duplicate.create_date >= original.create_date


def test_a_django_only_model_duplicates_its_row():
    export = IrExports.objects.create(name='Columnas', resource='x.Y')
    line = IrExportsLine.objects.create(name='amount', export=export)
    duplicate = line.copy({'name': 'amount_total'})
    assert duplicate.pk != line.pk
    assert (duplicate.name, duplicate.export_id) == ('amount_total', export.pk)


def test_every_own_concrete_model_has_copy():
    missing = [model._meta.label for model in apps.get_models()
               if not model.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)
               and not model._meta.proxy
               and not callable(getattr(model, 'copy', None))]
    assert missing == []
