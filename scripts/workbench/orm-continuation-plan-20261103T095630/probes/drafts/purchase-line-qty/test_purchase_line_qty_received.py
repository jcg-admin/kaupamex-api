"""La cantidad recibida de la línea de compra.

≙ ``odoo19c: addons/purchase/models/purchase_order_line.py:58-81,216-261,
707-713``. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/purchase-order-line-port.md`` (unidad 4).
"""
import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import connection
from django.utils import timezone

from addons.base.models import ResCompany, ResPartner
from orm.environments import context_scope, env, sudo
from orm.migration_operations import ComputeStoredFields
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db
LINE = 'purchase.order.line'


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def order():
    company = ResCompany.objects.create(name='Compras recibido 0122')
    vendor = ResPartner.objects.create(name='Proveedor recibido 0122')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    return order


def _line(order, **values):
    defaults = {'order_id': order.id, 'name': 'Insumo', 'product_qty': 5,
                'price_unit': Decimal('10')}
    if 'display_type' not in values and 'product_id' not in values:
        defaults['product_id'] = make_product(name='Insumo recibido').pk
    [line] = MODELS_BY_NAME[LINE].create([{**defaults, **values}])
    return line


def test_the_fields_of_the_unit():
    model = MODELS_BY_NAME[LINE]
    method = model._meta.get_field('qty_received_method')
    assert [key for key, _ in method.choices] == ['manual']
    for name in ('qty_received', 'qty_received_manual'):
        field = model._meta.get_field(name)
        assert field.decimal_places == 4, name
    assert model._fields['qty_received_manual'].copy is False
    assert model._fields['qty_received'].compute_sudo is True
    assert model._fields['qty_received_at_date'].store is False


def test_a_consumable_and_a_service_are_received_manually(order):
    consumable = _line(order, product_id=make_product(name='Consu R4').pk)
    service = _line(order, product_id=make_product(
        name='Servicio R4', type='service').pk)
    assert consumable.qty_received_method == 'manual'
    assert service.qty_received_method == 'manual'


def test_a_combo_and_a_section_have_no_method(order):
    combo = _line(order, product_id=make_product(
        name='Combo R4', type='combo').pk)
    section = _line(order, display_type='line_section', product_qty=0,
                    price_unit=Decimal('0'))
    assert not combo.qty_received_method
    assert not section.qty_received_method


def test_the_received_quantity_follows_the_manual_one(order):
    line = _line(order)
    assert line.qty_received == 0
    line.write({'qty_received_manual': Decimal('3')})
    line.flush_recordset()
    line.refresh_from_db()
    assert line.qty_received == Decimal('3')


def test_writing_the_received_quantity_feeds_the_manual_one(order):
    line = _line(order)
    line.write({'qty_received': Decimal('2.5')})
    line.flush_recordset()
    line.refresh_from_db()
    assert line.qty_received_manual == Decimal('2.5')
    assert line.qty_received == Decimal('2.5')


def test_the_inverse_clears_the_manual_quantity_without_method(order):
    line = _line(order, display_type='line_note', product_qty=0,
                 price_unit=Decimal('0'))
    line._inverse_qty_received()
    assert line.qty_received_manual == 0


def test_date_in_the_past():
    model = env()[LINE]
    assert model._date_in_the_past() is False
    yesterday = (timezone.localdate() - datetime.timedelta(days=1))
    with context_scope(accrual_entry_date=yesterday.isoformat()):
        assert env()[LINE]._date_in_the_past() is True
    with context_scope(accrual_entry_date=timezone.localdate().isoformat()):
        assert env()[LINE]._date_in_the_past() is False


def test_the_received_quantity_at_a_date(order):
    line = _line(order)
    line.write({'qty_received_manual': Decimal('4')})
    line.flush_recordset()
    assert line.qty_received_at_date == Decimal('4')


def test_the_received_quantity_at_a_past_date_is_recomputed(order):
    """Con ``accrual_entry_date`` en el pasado se recalcula con
    ``_prepare_qty_received`` en vez de copiar ``qty_received``
    (``odoo19c: :233-242``)."""
    line = _line(order)
    line.write({'qty_received_manual': Decimal('6')})
    line.flush_recordset()
    yesterday = (timezone.localdate() - datetime.timedelta(days=1))
    with context_scope(accrual_entry_date=yesterday.isoformat()):
        line.invalidate_recordset(['qty_received_at_date'])
        assert line._date_in_the_past() is True
        assert line.qty_received_at_date == Decimal('6')


def test_migration_0019_fills_the_existing_lines(order):
    """Las líneas existentes reciben su método y su cantidad recibida."""
    line = _line(order)
    line.write({'qty_received_manual': Decimal('3')})
    line.flush_recordset()
    model = type(line)
    model.objects.filter(pk=line.id).update(
        qty_received_method=None, qty_received=None)
    migration = importlib.import_module(
        'addons.purchase.migrations.0019_line_qty_received').Migration
    operation = migration.operations[-1]
    assert isinstance(operation, ComputeStoredFields)
    with connection.schema_editor() as editor:
        operation.code(apps, editor)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT qty_received_method, qty_received '
            'FROM purchase_order_line WHERE id = %s', [line.id])
        assert cursor.fetchone() == ('manual', Decimal('3.0000'))
