"""``ir.actions.act_window`` sobre ``models.BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:262-267`` (atributos),
``:309-331`` (``view_id`` y ``search_view_id``), ``:336-397`` (métodos) y
``odoo/addons/base/security/ir.model.access.csv:101``. Diseño:
``designs/ir-actions-act-window-basemodel.md``.
"""

import pytest

import models
from addons.base.models import IrModelData, ResGroups, ResPartner, ResUsers
from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.ir_ui_view import IrUiView
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _user(login, xmlid):
    with sudo():
        partner = ResPartner.objects.create(name=login, email='')
        user = ResUsers.objects.create(login=login, partner=partner)
        user.group_ids.set([ResGroups.objects.get(
            pk=IrModelData._xmlid_to_res_id(xmlid, raise_if_not_found=True))])
    return user


def _system_env():
    user = _user('act-window-system@kaupamex.test', 'base.group_system')
    return user, Environment(uid=user.pk)['ir.actions.act_window']


def test_the_window_action_is_a_basemodel_with_the_source_attributes():
    assert issubclass(IrActionsActWindow, models.BaseModel)
    assert (IrActionsActWindow._name, IrActionsActWindow._description,
            IrActionsActWindow._table, IrActionsActWindow._order,
            IrActionsActWindow._allow_sudo_commands) == (
        'ir.actions.act_window', 'Action Window', 'ir_act_window',
        'name, id', False)


def test_a_system_user_creates_a_window_action():
    """ACL de ``group_system`` (``ir.model.access.csv:101``)."""
    user, env = _system_env()
    with user_scope(user.pk):
        action = env.create({'name': 'Socios', 'res_model': 'res.partner'})
    assert IrActionsActWindow.objects.filter(pk=action.id).exists()


def test_an_internal_user_cannot_read_window_actions():
    user = _user('act-window-internal@kaupamex.test', 'base.group_user')
    with user_scope(user.pk):
        env = Environment(uid=user.pk)['ir.actions.act_window']
        with pytest.raises(AccessError):
            env.browse().check_access('read')


def test_an_unnamed_action_takes_the_description_of_its_model():
    """``create`` (``ir_actions.py:357-363``)."""
    user, env = _system_env()
    with user_scope(user.pk):
        action = env.create({'res_model': 'res.partner'})
    assert IrActionsActWindow.objects.get(pk=action.id).name == (
        ResPartner._description)


def test_the_view_of_view_id_goes_first_among_the_missing_modes():
    """``_compute_views`` (``ir_actions.py:282-296``): con ``view_id``
    de un modo que falta en ``view_ids``, ese modo se adelanta."""
    with sudo():
        form = IrUiView.objects.create(
            name='partner.form.3a', type='form', model='res.partner',
            arch_db='<form/>')
        action = IrActionsActWindow.create({
            'name': 'Socios', 'res_model': 'res.partner',
            'view_mode': 'list,form', 'view_id': form.pk})
        assert action.views == [(form.pk, 'form'), (None, 'list')]


def test_exists_drops_an_unlinked_action():
    """``exists`` y ``_existing`` (``ir_actions.py:369-378``): ``unlink``
    limpia la caché memorizada."""
    with sudo():
        first = IrActionsActWindow.create(
            {'name': 'Uno', 'res_model': 'res.partner'})
        second = IrActionsActWindow.create(
            {'name': 'Dos', 'res_model': 'res.partner'})
        model = Environment()['ir.actions.act_window']
        both = model.browse([first.id, second.id])
        assert both.exists().ids == [first.id, second.id]
        first.unlink()
        assert model.browse(
            [first.id, second.id]).exists().ids == [second.id]


def test_the_readable_fields_name_the_source_set():
    """``_get_readable_fields`` (``ir_actions.py:380-386``)."""
    readable = IrActionsActWindow._get_readable_fields(
        IrActionsActWindow())
    assert {'view_id', 'search_view_id', 'embedded_action_ids', 'views',
            'res_model', 'close_on_report_download'} <= readable
