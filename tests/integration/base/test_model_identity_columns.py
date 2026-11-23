"""Las columnas que nombran modelos guardan su identidad contractual.

≙ ``'model': model._name``
(``odoo19c: odoo/addons/base/models/ir_model.py:428``).
Corte C3 de ``designs/model-identity-contract.md``: el reflejo, las siembras y
los cotejos escriben y leen ``registry.identity_of``; la migración
``base.0128`` reescribe las filas que guardaban la etiqueta de Django.
"""
import types

import pytest
from django.db import connection

from addons.base.models.ir_cron import IrCron
from addons.base.models.ir_model import IrModel, IrModelData, IrModelFields
from addons.base.models.ir_rule import IrRule
from addons.base_automation.models.signals import _model_name
from addons.sale.models.sale_order import SaleOrder
from addons.stock.models.stock_picking import StockPicking
from orm import registry
from orm.migration_operations import RewriteModelIdentities

pytestmark = pytest.mark.django_db


def test_stock_picking_is_found_by_its_name():
    assert IrModel.objects.filter(model='stock.picking').count() == 1


def test_the_django_label_no_longer_matches_ir_model():
    # Control negativo: la etiqueta de Django ya no es la llave de la fila.
    assert StockPicking._meta.label == 'stock.StockPicking'
    assert not IrModel.objects.filter(
        model=StockPicking._meta.label).exists()
    assert not IrModel.objects.filter(
        model__in=[m._meta.label for m in (StockPicking, SaleOrder, IrCron)]
    ).exists()


def test_reflection_writes_the_fields_under_the_identity():
    field = IrModelFields.objects.get(model='stock.picking', name='company')
    assert field.relation == 'res.company'
    assert field.model_id.model == 'stock.picking'


def test_rules_are_found_by_either_spelling():
    by_name = list(
        IrRule._get_rules('sale.order').values_list('pk', flat=True))
    by_label = list(
        IrRule._get_rules('sale.SaleOrder').values_list('pk', flat=True))
    assert by_name
    assert by_name == by_label


def test_the_seeded_rule_stores_the_identity():
    assert IrRule.objects.filter(
        name='Sales Order multi-company', model_name='sale.order').exists()


def test_the_cron_xml_id_stores_the_identity():
    row = IrModelData.objects.get(module='base', name='autovacuum_job')
    assert row.model == 'ir.cron' == registry.identity_of(IrCron)


def test_automation_triggers_name_the_model_by_its_identity():
    assert _model_name(SaleOrder) == 'sale.order'


def _schema_editor():
    return types.SimpleNamespace(connection=connection)


def _scratch_table(rows):
    with connection.cursor() as cr:
        cr.execute('CREATE TEMP TABLE identity_probe '
                   '(id serial, model varchar, name varchar)')
        cr.executemany(
            'INSERT INTO identity_probe (model, name) VALUES (%s, %s)', rows)


def _scratch_rows():
    with connection.cursor() as cr:
        cr.execute('SELECT model, name FROM identity_probe ORDER BY id')
        return cr.fetchall()


def test_the_rewrite_turns_labels_into_identities():
    _scratch_table([('sale.SaleOrder', 'a'), ('sale.order', 'b'),
                    ('nowhere.Nothing', 'c')])
    RewriteModelIdentities('identity_probe', 'model')._rewrite(
        None, _schema_editor())
    assert _scratch_rows() == [('sale.order', 'a'), ('sale.order', 'b'),
                               ('nowhere.Nothing', 'c')]


def test_the_rewrite_refuses_to_duplicate_a_unique_key():
    _scratch_table([('sale.SaleOrder', 'state'), ('sale.order', 'state')])
    operation = RewriteModelIdentities('identity_probe', 'model',
                                       unique_with=['model', 'name'])
    with pytest.raises(ValueError, match='identity_probe.model'):
        operation._rewrite(None, _schema_editor())
    assert _scratch_rows() == [('sale.SaleOrder', 'state'),
                               ('sale.order', 'state')]
