"""``act_window.view``, ``act_url`` y ``client`` sobre ``models.BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:411-425``
(``act_window.view``), ``:445-460`` (``act_url``), ``:1426-1462``
(``client``) y ``odoo/addons/base/security/ir.model.access.csv:105-110``.
Diseño: ``designs/ir-actions-view-url-client-basemodel.md``.
"""

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

import models
from addons.base.models import IrModelData, ResGroups, ResPartner, ResUsers
from addons.base.models.ir_actions import (
    IrActionsActUrl, IrActionsActWindow, IrActionsActWindowView,
    IrActionsClient)
from addons.base.models.ir_ui_view import IrUiView
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

MODELS = [
    (IrActionsActWindowView, 'ir.actions.act_window.view',
     'Action Window View', 'ir_act_window_view', 'sequence,id'),
    (IrActionsActUrl, 'ir.actions.act_url', 'Action URL', 'ir_act_url',
     'name, id'),
    (IrActionsClient, 'ir.actions.client', 'Client Action', 'ir_act_client',
     'name, id'),
]


def _user(login, xmlid):
    with sudo():
        partner = ResPartner.objects.create(name=login, email='')
        user = ResUsers.objects.create(login=login, partner=partner)
        user.group_ids.set([ResGroups.objects.get(
            pk=IrModelData._xmlid_to_res_id(xmlid, raise_if_not_found=True))])
    return user


@pytest.mark.parametrize('model, name, description, table, order', MODELS)
def test_each_model_is_a_basemodel_with_the_source_attributes(
        model, name, description, table, order):
    assert issubclass(model, models.BaseModel)
    assert (model._name, model._description, model._table, model._order,
            model._allow_sudo_commands) == (
        name, description, table, order, False)


def test_the_window_view_names_its_record_by_view_id():
    assert IrActionsActWindowView._rec_name == 'view_id'


@pytest.mark.parametrize('model', [row[1] for row in MODELS])
def test_an_internal_user_cannot_read_them(model):
    """ACL de ``group_system`` (``ir.model.access.csv:105-110``)."""
    user = _user(f'{model}-internal@kaupamex.test', 'base.group_user')
    with user_scope(user.pk):
        with pytest.raises(AccessError):
            Environment(uid=user.pk)[model].browse().check_access('read')


def test_views_reads_the_view_declared_in_view_ids():
    """``_compute_views`` (``ir_actions.py:282-296``) sobre ``view_ids``,
    cuyo ``view_id`` es Many2one a ``ir.ui.view`` (``:421``)."""
    with sudo():
        form = IrUiView.objects.create(
            name='partner.form.3c', type='form', model='res.partner',
            arch_db='<form/>')
        action = IrActionsActWindow.create({
            'name': 'Socios', 'res_model': 'res.partner',
            'view_mode': 'form'})
        IrActionsActWindowView.create({
            'act_window_id': action.id, 'view_id': form.pk,
            'view_mode': 'form'})
        assert action.views == [(form.pk, 'form')]
    field = IrActionsActWindowView._meta.get_field('view_id')
    assert field.related_model is IrUiView
    assert IrActionsActWindowView._meta.get_field(
        'act_window_id').related_model is IrActionsActWindow


def test_client_params_round_trip_through_params_store():
    """``_compute_params`` y ``_inverse_params``
    (``ir_actions.py:1449-1457``)."""
    with sudo():
        client = IrActionsClient.create(
            {'name': 'Tablero', 'tag': 'dashboard', 'params': {'a': 1}})
        row = IrActionsClient.objects.get(pk=client.id)
        assert bytes(row.params_store) == b"{'a': 1}"
        assert client.params == {'a': 1}


def test_the_readable_fields_name_the_source_sets():
    assert {'target', 'url', 'close'} <= IrActionsActUrl._get_readable_fields(
        IrActionsActUrl())
    assert {'context', 'params', 'res_model', 'tag', 'target'} <= (
        IrActionsClient._get_readable_fields(IrActionsClient()))


def test_stored_json_params_become_a_python_literal():
    """La migración reescribe ``params_store`` guardado como JSON con
    ``repr`` del dict, que es lo que ``_compute_params`` evalúa."""
    with sudo():
        client = IrActionsClient.create({'name': 'T', 'tag': 'x'})
    IrActionsClient.objects.filter(pk=client.id).update(
        params_store=b'{"a": true}')
    migration = importlib.import_module(
        'addons.base.migrations.0143_ir_actions_view_url_client')
    migration.params_as_python_literal(
        django_apps, SimpleNamespace(connection=connection))
    assert bytes(IrActionsClient.objects.get(pk=client.id).params_store) == (
        b"{'a': True}")
