"""``parent_state`` de ``account.move.line``: el estado del asiento.

≙ ``odoo19c: addons/account/models/account_move_line.py:68``
``parent_state = fields.Selection(related='move_id.state', store=True)``.
Lo citan la regla ``account_invoice_line_rule_portal`` de
``account/security/account_security.xml`` y el propio modelo
(``:885``, las líneas en borrador).
"""
import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import connection
from django.utils import timezone

from addons.account.models import AccountJournal, AccountMove, AccountMoveLine
from addons.base.models import ResCompany
from orm.environments import Environment, get_transaction
from orm.migration_operations import ComputeStoredFields
from orm.utils import SUPERUSER_ID, model_field_registry

pytestmark = pytest.mark.django_db


@pytest.fixture
def move():
    company = ResCompany.objects.create(name='Estado padre', code='parent-st')
    journal = AccountJournal.objects.create(
        name='Varios', code='PST', type='general', company=company)
    return AccountMove.objects.create(
        date=timezone.now().date(), journal=journal, company=company)


def test_the_field_is_a_stored_related_of_the_move_state():
    field = model_field_registry(AccountMoveLine)['parent_state']
    assert field.related == 'move_id.state'
    assert field.store is True


def test_a_new_line_takes_the_state_of_its_move(move):
    line = AccountMoveLine.objects.create(
        move=move, debit=Decimal('5.00'), credit=Decimal('0.00'))
    line.refresh_from_db()
    assert line.parent_state == 'draft'


def test_the_column_follows_a_change_of_the_move_state(move):
    line = AccountMoveLine.objects.create(
        move=move, debit=Decimal('5.00'), credit=Decimal('0.00'))
    with Environment('default', SUPERUSER_ID, {}):
        move.state = 'cancel'
        move.save()
        get_transaction().flush()
    stored = AccountMoveLine.objects.filter(pk=line.pk).values_list(
        'parent_state', flat=True).get()
    assert stored == 'cancel'


def test_migration_0039_fills_the_existing_lines(move):
    """Filas anteriores a la columna: la operación de 0039 les da el estado de
    su asiento. Se lee con SQL: la lectura del ORM devolvería la caché."""
    line = AccountMoveLine.objects.create(
        move=move, debit=Decimal('5.00'), credit=Decimal('0.00'))
    get_transaction().flush()
    AccountMove.objects.filter(pk=move.pk).update(state='cancel')
    AccountMoveLine.objects.filter(pk=line.pk).update(parent_state=None)
    operation = importlib.import_module(
        'addons.account.migrations.0039_parent_state').Migration.operations[1]
    assert isinstance(operation, ComputeStoredFields)
    with connection.schema_editor() as editor:
        operation.code(apps, editor)
    with connection.cursor() as cursor:
        cursor.execute('SELECT parent_state FROM account_move_line '
                       'WHERE id = %s', [line.pk])
        assert cursor.fetchone() == ('cancel',)
