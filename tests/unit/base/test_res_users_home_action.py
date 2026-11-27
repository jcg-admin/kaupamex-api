"""``res.users.action_id``, ``_check_action_id`` y
``_unlink_check_home_action``.

≙ ``odoo19c: odoo/addons/base/models/res_users.py:183,193,229-230,512-533``
y ``odoo/addons/base/models/ir_actions.py:134-136``.
Diseño: ``designs/res-users-home-action.md``.
"""

import pytest
from django.core.exceptions import ValidationError

from addons.base.models import ResPartner, ResUsers
from addons.base.models.ir_actions import (
    IrActionsActions, IrActionsActWindow, IrActionsClient)
from orm.environments import Environment, sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    """El ``TransactionCase`` de la fuente corre como superusuario."""
    with sudo():
        yield


def _user(login):
    partner = ResPartner.objects.create(name=login, email='')
    return ResUsers.objects.create(login=login, partner=partner)


def test_action_id_is_the_home_action_column():
    field = ResUsers._meta.get_field('action_id')
    assert (field.name, field.column, field.related_model,
            field.verbose_name) == (
        'action_id', 'action_id', IrActionsActions, 'Home Action')


def test_action_id_is_self_readable_and_writeable():
    """``SELF_READABLE_FIELDS`` y ``SELF_WRITEABLE_FIELDS``
    (``res_users.py:183,193``)."""
    user = ResUsers()
    assert 'action_id' in user.SELF_READABLE_FIELDS
    assert 'action_id' in user.SELF_WRITEABLE_FIELDS


def test_a_reload_client_action_cannot_be_the_home_action():
    """``_check_action_id`` (``:518-523``)."""
    reload_action = IrActionsClient.create(
        {'name': 'Recargar', 'tag': 'reload'})
    user = _user('home-reload@kaupamex.test')
    user.action_id_id = reload_action.id
    with pytest.raises(ValidationError):
        user.clean()


def test_a_window_action_needing_active_id_cannot_be_the_home_action():
    """``_check_action_id`` (``:525-533``)."""
    window = IrActionsActWindow.create({
        'name': 'Con registro', 'res_model': 'res.partner',
        'context': "{'default_partner_id': active_id}"})
    user = _user('home-active@kaupamex.test')
    user.action_id_id = window.id
    with pytest.raises(ValidationError):
        user.clean()


def test_a_plain_window_action_is_accepted():
    window = IrActionsActWindow.create(
        {'name': 'Socios', 'res_model': 'res.partner'})
    user = _user('home-plain@kaupamex.test')
    user.action_id_id = window.id
    user.clean()


def test_deleting_the_action_clears_the_home_action_of_every_user():
    """``_unlink_check_home_action`` (``ir_actions.py:134-136``): también los
    usuarios archivados."""
    window = IrActionsActWindow.create(
        {'name': 'Inicio', 'res_model': 'res.partner'})
    active = _user('home-active-user@kaupamex.test')
    archived = _user('home-archived-user@kaupamex.test')
    ResUsers.objects.filter(pk__in=[active.pk, archived.pk]).update(
        action_id=window.id)
    ResUsers.objects.filter(pk=archived.pk).update(active=False)
    Environment()['ir.actions.act_window'].browse(window.id).unlink()
    assert list(ResUsers.objects.filter(
        pk__in=[active.pk, archived.pk]).values_list(
            'action_id', flat=True)) == [None, None]


@pytest.mark.parametrize('model, values, expected', [
    ('ir.actions.act_window', {'res_model': 'res.partner'},
     'ir.actions.act_window'),
    ('ir.actions.act_url', {'url': '/x'}, 'ir.actions.act_url'),
    ('ir.actions.client', {'tag': 'x'}, 'ir.actions.client'),
])
def test_each_subtype_defaults_its_type(model, values, expected):
    """Cada subtipo redeclara ``type`` con su valor por defecto
    (``ir_actions.py:308,453,1434``)."""
    record = Environment()[model].create({'name': 'Por defecto', **values})
    assert record.type == expected


@pytest.mark.parametrize('model, field, expected', [
    ('ir.actions.server', 'type', 'ir.actions.server'),
    ('ir.actions.report', 'type', 'ir.actions.report'),
    ('ir.actions.report', 'binding_type', 'report'),
])
def test_the_declared_defaults_of_server_and_report(model, field, expected):
    """``ir_actions.py:607`` e ``ir_actions_report.py:165-166``."""
    assert Environment()[model]._fields[field].default == expected
