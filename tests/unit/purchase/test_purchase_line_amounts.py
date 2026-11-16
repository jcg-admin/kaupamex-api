"""Los importes de la línea de compra salen del motor de ``account.tax``.

≙ ``odoo19c: addons/purchase/models/purchase_order_line.py:23,34,46-48,
106-143``. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/purchase-order-line-port.md`` (unidad 1).
"""
import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import connection

from addons.account.models import AccountTax
from addons.base.models import ResCompany, ResPartner
from orm.environments import get_transaction, sudo
from orm.migration_operations import ComputeStoredFields
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


@pytest.fixture
def company():
    return ResCompany.objects.create(name='Compras importes 0122')


def _tax(company, price_include=False):
    return AccountTax.objects.create(
        name='IVA 16', amount=Decimal('16'), company=company,
        type_tax_use='purchase', price_include=price_include)


def _line(company, taxes=(), price='100', qty='2', discount='0'):
    vendor = ResPartner.objects.create(name='Proveedor importes 0122')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    [line] = MODELS_BY_NAME['purchase.order.line'].create([{
        'order_id': order.id, 'name': 'Insumo',
        'product_id': make_product(name='Insumo importes').pk,
        'price_unit': Decimal(price), 'product_qty': Decimal(qty),
        'discount': Decimal(discount),
        'tax_ids': [(6, 0, [tax.pk for tax in taxes])]}])
    return line


def test_tax_ids_use_the_source_relation_table():
    field = MODELS_BY_NAME['purchase.order.line']._meta.get_field('tax_ids')
    assert field.remote_field.through._meta.db_table == (
        'account_tax_purchase_order_line_rel')


def test_product_qty_is_a_required_quantity_without_default():
    field = MODELS_BY_NAME['purchase.order.line']._meta.get_field(
        'product_qty')
    assert not field.null
    assert not field.has_default()
    assert field.decimal_places == 4


def test_a_line_without_taxes_carries_no_tax(company):
    line = _line(company, price='100', qty='2.5')
    assert line.price_subtotal == Decimal('250.00')
    assert line.price_total == Decimal('250.00')
    assert line.price_tax == Decimal('0.00')


def test_an_excluded_tax_adds_on_top(company):
    line = _line(company, taxes=[_tax(company)])
    assert line.price_subtotal == Decimal('200.00')
    assert line.price_tax == Decimal('32.00')
    assert line.price_total == Decimal('232.00')


def test_an_included_tax_is_taken_out_of_the_price(company):
    line = _line(company, taxes=[_tax(company, price_include=True)],
                 price='116')
    assert line.price_subtotal == Decimal('200.00')
    assert line.price_tax == Decimal('32.00')
    assert line.price_total == Decimal('232.00')


def test_the_discount_applies_before_the_tax(company):
    line = _line(company, taxes=[_tax(company)], discount='10')
    assert line.price_subtotal == Decimal('180.00')
    assert line.price_total == Decimal('208.80')


def test_writing_the_price_recomputes_the_stored_amounts(company):
    line = _line(company, taxes=[_tax(company)])
    line.write({'price_unit': Decimal('50')})
    line.flush_recordset()
    line.refresh_from_db()
    assert line.price_subtotal == Decimal('100.00')
    assert line.price_total == Decimal('116.00')


def test_the_order_sums_the_line_columns(company):
    line = _line(company, taxes=[_tax(company)])
    order = line.order_id
    assert order.amount_untaxed() == Decimal('200.00')
    assert order.amount_tax() == Decimal('32.00')
    assert order.amount_total() == Decimal('232.00')


def test_migration_0017_fills_the_existing_lines(company):
    """Las líneas existentes reciben sus importes y su ``price_total_cc``."""
    line = _line(company, taxes=[_tax(company)])
    get_transaction().flush()
    type(line).objects.filter(pk=line.pk).update(
        price_subtotal=None, price_total=None, price_tax=None,
        price_total_cc=None)
    migration = importlib.import_module(
        'addons.purchase.migrations.0017_line_amounts').Migration
    operation = migration.operations[-1]
    assert isinstance(operation, ComputeStoredFields)
    with connection.schema_editor() as editor:
        operation.code(apps, editor)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT price_subtotal, price_tax, price_total, price_total_cc '
            'FROM purchase_order_line WHERE id = %s', [line.pk])
        row = cursor.fetchone()
    assert row == (Decimal('200.00'), Decimal('32.00'), Decimal('232.00'),
                   Decimal('200.00'))
