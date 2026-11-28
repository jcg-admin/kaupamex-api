"""Grupo A de ``ir.module.module``: estado y siguiente paso.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py`` — ``:57-74``
(``assert_log_admin_access``), ``:347-349``, ``:495-505``, ``:581-597`` y
``:912-919``. Diseño: ``designs/ir-module-group-a.md``.
"""

import pytest

from addons.base.models import IrActionsTodo, IrModule
from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.res_users import ResUsers
from exceptions import AccessDenied
from orm.environments import Environment, sudo, user_scope
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _modules():
    # El entorno de instalación de la fuente: ``SUPERUSER_ID``, con
    # ``env.user``.
    return Environment(uid=SUPERUSER_ID)['ir.module.module']


def _module(name, state):
    return IrModule.objects.create(name=name, shortdesc=name, state=state)


def test_the_registry_loads_the_installed_modules():
    assert _modules()._get_modules_to_load_domain() == [
        ('state', '=', 'installed')]


def test_reset_state_returns_transient_states_to_their_origin():
    pending = _module('ga_pending', 'to install')
    upgrading = _module('ga_upgrading', 'to upgrade')
    removing = _module('ga_removing', 'to remove')
    with sudo():
        assert _modules().button_reset_state() is True
    for module, state in ((pending, 'uninstalled'),
                          (upgrading, 'installed'),
                          (removing, 'installed')):
        module.refresh_from_db()
        assert module.state == state


def test_reset_state_is_denied_to_a_non_admin():
    _module('ga_denied', 'to install')
    with sudo():
        user = ResUsers.objects.create_user(
            login='ga-internal@kaupamex.test', password='x')
    with user_scope(user.pk), pytest.raises(AccessDenied):
        Environment(uid=user.pk)['ir.module.module'].button_reset_state()
    assert IrModule.objects.get(name='ga_denied').state == 'to install'


def test_check_module_update_sees_a_transient_module():
    IrModule.objects.filter(
        state__in=('to install', 'to upgrade', 'to remove')).update(
            state='uninstalled')
    assert _modules().check_module_update() is False
    _module('ga_update', 'to upgrade')
    assert _modules().check_module_update() is True


def test_installed_maps_names_to_ids():
    module = _module('ga_installed', 'installed')
    _modules().env.registry.clear_cache('stable')
    installed = _modules()._installed()
    assert installed['ga_installed'] == module.id
    assert 'ga_pending_absent' not in installed


def test_next_launches_the_open_step():
    with sudo():
        IrActionsTodo.search([('state', '=', 'open')]).write(
            {'state': 'done'})
        window = IrActionsActWindow.create({
            'name': 'Asistente', 'res_model': 'res.partner',
            'view_mode': 'form'})
        step = IrActionsTodo.create({'action_id': window.id})
        result = _modules().next()
    assert result['id'] == window.id
    assert step.state == 'done'


def test_next_without_open_step_goes_home():
    with sudo():
        IrActionsTodo.search([('state', '=', 'open')]).write(
            {'state': 'done'})
        assert _modules().next() == {
            'type': 'ir.actions.act_url', 'target': 'self', 'url': '/odoo'}
