"""``group_ids``, ``context`` y ``read`` de ``ir.actions.act_window``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:312-313`` (``context``),
``:328-329`` (``group_ids``), ``:341-355`` (``read``) y
``odoo/addons/base/models/ir_ui_view.py:2747-2758``
(``get_empty_list_help``). Diseño:
``designs/ir-actions-act-window-groups-context-read.md``.
"""

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

import models
from addons.base.models import IrModelData, ResGroups
from addons.base.models.ir_actions import (
    IrActionsActWindow, IrActionsServer)
from orm.environments import sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    """≙ ``TransactionCase`` de la fuente, que corre como superusuario."""
    with sudo():
        yield


def _group():
    return ResGroups.objects.get(pk=IrModelData._xmlid_to_res_id(
        'base.group_user', raise_if_not_found=True))


def test_group_ids_uses_the_source_relation_and_columns():
    group = _group()
    action = IrActionsActWindow.create({
        'name': 'Socios', 'res_model': 'res.partner',
        'group_ids': [group.pk]})
    with connection.cursor() as cr:
        cr.execute('SELECT act_id, gid FROM ir_act_window_group_rel '
                   'WHERE act_id = %s', [action.id])
        assert cr.fetchall() == [(action.id, group.pk)]
    assert list(action.group_ids.values_list('pk', flat=True)) == [group.pk]


def test_context_is_text_with_the_source_default():
    action = IrActionsActWindow.create(
        {'name': 'Socios', 'res_model': 'res.partner'})
    assert action.context == '{}'
    field = IrActionsActWindow._meta.get_field('context')
    assert field.get_internal_type() in ('CharField', 'TextField')


def test_read_asks_the_target_model_for_its_empty_list_help(monkeypatch):
    """``read`` (``ir_actions.py:341-355``): con ``help`` pedido, el
    resultado es lo que ``get_empty_list_help`` del modelo destino devuelve,
    con el ``context`` de la acción en el entorno."""
    seen = {}

    def probe(self, help_message):
        seen['flag'] = self.env.context.get('probe_flag')
        return help_message + ' (vacía)'

    monkeypatch.setattr(IrActionsServer, 'get_empty_list_help', probe)
    action = IrActionsActWindow.create({
        'name': 'Acciones', 'res_model': 'ir.actions.server',
        'help': '<p>Sin socios</p>', 'context': "{'probe_flag': True}"})
    (values,) = action.read(['help', 'res_model', 'context'])
    assert values['help'] == '<p>Sin socios</p> (vacía)'
    assert seen == {'flag': True}


def test_the_base_empty_list_help_returns_the_message():
    """``get_empty_list_help`` del modelo ``base``
    (``ir_ui_view.py:2747-2758``)."""
    assert models.BaseModel.get_empty_list_help(
        IrActionsActWindow(), '<p>x</p>') == '<p>x</p>'


def test_a_json_context_becomes_a_python_literal():
    """La migración ``0142`` reescribe el JSON guardado con ``repr`` del
    dict: ``{'a': True}``, no ``{"a": true}``."""
    action = IrActionsActWindow.create(
        {'name': 'Socios', 'res_model': 'res.partner'})
    IrActionsActWindow.objects.filter(pk=action.id).update(
        context='{"a": true, "b": null}')
    migration = importlib.import_module(
        'addons.base.migrations.0142_ir_actions_act_window_groups_context')
    migration.context_as_python_literal(
        django_apps, SimpleNamespace(connection=connection))
    assert IrActionsActWindow.objects.get(pk=action.id).context == (
        "{'a': True, 'b': None}")
