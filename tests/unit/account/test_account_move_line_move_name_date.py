"""``move_name`` y ``date`` de ``account.move.line``.

≙ ``odoo19c: addons/account/models/account_move_line.py:63``
``move_name = fields.Char(related='move_id.name', store=True)`` y
``odoo19c: addons/account/models/account_move_line.py:69``
``date = fields.Date(related='move_id.date', store=True)``. Son los dos
campos que cita ``_order = "date desc, move_name desc, id"`` (``:35``).

Métrica: las columnas ``move_name`` y ``date`` leídas de la base.
Ciega a: ``invoice_date`` y ``ref``, que no están portados.
"""
import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import connection

from addons.account.models import AccountJournal, AccountMove, AccountMoveLine
from addons.base.models import ResCompany
from orm.environments import Environment, get_transaction
from orm.migration_operations import ComputeStoredFields
from orm.utils import SUPERUSER_ID, model_field_registry

pytestmark = pytest.mark.django_db

DAY = datetime.date(2026, 3, 14)


@pytest.fixture
def move():
    company = ResCompany.objects.create(name='Nombre padre', code='parent-nm')
    journal = AccountJournal.objects.create(
        name='Varios', code='PNM', type='general', company=company)
    return AccountMove.objects.create(
        date=DAY, journal=journal, company=company, name='MISC/0001')


def _line(move):
    return AccountMoveLine.objects.create(
        move=move, debit=Decimal('5.00'), credit=Decimal('0.00'))


def _stored(line):
    return AccountMoveLine.objects.filter(pk=line.pk).values_list(
        'move_name', 'date').get()


@pytest.mark.parametrize('name, related', [
    ('move_name', 'move_id.name'),
    ('date', 'move_id.date'),
])
def test_the_field_is_a_stored_related_of_the_move(name, related):
    field = model_field_registry(AccountMoveLine)[name]
    assert field.related == related
    assert field.store is True


def test_date_is_not_copied():
    assert model_field_registry(AccountMoveLine)['date'].copy is False


def test_a_new_line_takes_both_from_its_move(move):
    line = _line(move)
    get_transaction().flush()
    assert _stored(line) == ('MISC/0001', DAY)


def test_the_columns_follow_a_change_of_the_move(move):
    line = _line(move)
    later = DAY + datetime.timedelta(days=3)
    with Environment('default', SUPERUSER_ID, {}):
        move.name = 'MISC/0002'
        move.date = later
        move.save()
        get_transaction().flush()
    assert _stored(line) == ('MISC/0002', later)


def test_migration_0046_fills_the_existing_lines(move):
    """Filas anteriores a las columnas: la operación de 0046 les da el
    número y la fecha de su asiento. Se lee con SQL: la lectura del ORM
    devolvería la caché."""
    line = _line(move)
    get_transaction().flush()
    AccountMoveLine.objects.filter(pk=line.pk).update(
        move_name=None, date=None)
    operation = importlib.import_module(
        'addons.account.migrations.0046_move_line_move_name_date'
    ).Migration.operations[-1]
    assert isinstance(operation, ComputeStoredFields)
    with connection.schema_editor() as editor:
        operation.code(apps, editor)
    with connection.cursor() as cursor:
        cursor.execute('SELECT move_name, date FROM account_move_line '
                       'WHERE id = %s', [line.pk])
        assert cursor.fetchone() == ('MISC/0001', DAY)
