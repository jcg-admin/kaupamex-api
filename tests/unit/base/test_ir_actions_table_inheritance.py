"""Las tablas de los subtipos de acción heredan de ``ir_actions``.

≙ ``odoo19c: odoo/addons/base/data/base_data.sql:5-13`` (``INHERITS
(ir_actions)``) y ``odoo/orm/fields_relational.py:313-314`` (sin clave
foránea hacia ``ir_actions``). Diseño:
``designs/ir-actions-family-basemodel-and-inheritance.md`` (paso 1).
"""

import pytest
from django.apps import apps
from django.db import connection

from addons.base.models.ir_actions import (IrActionsActions,
                                           IrActionsActWindow,
                                           IrActionsServer, IrActionsTodo)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

SUBTYPE_TABLES = ('ir_act_window', 'ir_act_report_xml', 'ir_act_url',
                  'ir_act_server', 'ir_act_client')


@pytest.mark.parametrize('table', SUBTYPE_TABLES)
def test_the_subtype_table_inherits_ir_actions(table):
    with connection.cursor() as cr:
        cr.execute(
            "SELECT 1 FROM pg_inherits WHERE inhrelid = %s::regclass "
            "AND inhparent = 'ir_actions'::regclass", [table])
        assert cr.fetchone() is not None


def test_ir_actions_sees_a_subtype_row():
    window = IrActionsActWindow.objects.create(
        name='inherit-window', type='ir.actions.act_window',
        res_model='base.ResPartner')
    with connection.cursor() as cr:
        cr.execute('SELECT 1 FROM ir_actions WHERE id = %s', [window.pk])
        assert cr.fetchone() is not None


@pytest.mark.parametrize('table', SUBTYPE_TABLES)
def test_the_subtype_draws_ids_from_the_ir_actions_sequence(table):
    """Una sola secuencia: dos subtipos nunca reparten el mismo id."""
    with connection.cursor() as cr:
        cr.execute(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'id'", [table])
        [default] = cr.fetchone()
        cr.execute("SELECT pg_get_serial_sequence('ir_actions', 'id')")
        [sequence] = cr.fetchone()
    # ``pg_get_serial_sequence`` califica con el esquema y el default no.
    assert default == f"nextval('{sequence.split('.')[-1]}'::regclass)"


def test_a_wizard_step_can_point_at_a_window_action():
    window = IrActionsActWindow.objects.create(
        name='inherit-todo-window', type='ir.actions.act_window',
        res_model='base.ResPartner')
    step = IrActionsTodo.objects.create(action_id_id=window.pk)
    assert IrActionsTodo.objects.filter(pk=step.pk).exists()


def test_no_foreign_key_points_at_ir_actions():
    """``fields_relational.py:313-314``: ninguna clave foránea hacia
    ``ir_actions``, ni en los campos ni en la base."""
    declared = sorted(
        f'{model._meta.label}.{field.name}'
        for model in apps.get_models()
        for field in model._meta.local_fields
        if field.is_relation and field.many_to_one
        and field.related_model._meta.db_table == 'ir_actions'
        and field.db_constraint)
    assert declared == []
    with connection.cursor() as cr:
        cr.execute(
            "SELECT conname FROM pg_constraint WHERE contype = 'f' "
            "AND confrelid = 'ir_actions'::regclass")
        assert cr.fetchall() == []


def test_the_server_actions_keep_their_ids():
    """Las filas existentes no se renumeran."""
    before = sorted(IrActionsServer.objects.values_list('pk', flat=True))
    assert before == sorted(set(before))
