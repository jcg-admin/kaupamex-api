"""``res.users.deletion`` sobre ``models.BaseModel``, con su barrido.

≙ ``odoo19c: odoo/addons/base/models/res_users_deletion.py:11-100`` y
``odoo/addons/base/security/ir.model.access.csv:87-88``. Diseño:
``designs/basemodel-adoption-res-users-deletion.md``.
"""

import pytest

from addons.base.models.ir_cron import IrCron
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from addons.base.models.res_users_deletion import ResUsersDeletion
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _env():
    return Environment(su=True)['res.users.deletion']


def _user(login):
    with sudo():
        partner = ResPartner.objects.create(name=login, email='')
        return ResUsers.objects.create(login=login, partner=partner)


def _request(user):
    return _env().create({'user': user.pk, 'user_int': user.pk})


def test_a_request_without_user_is_marked_done():
    """Las solicitudes cuyo usuario ya no existe (``:47-49``)."""
    orphan = _env().create({'user_int': 999999})
    _env()._gc_portal_users()
    orphan.invalidate_recordset()
    assert orphan.state == 'done'


def test_the_sweep_deletes_the_user_and_the_partner():
    """Paso 1 y paso 2 (``:65-100``)."""
    user = _user('gc-portal@kaupamex.test')
    partner_id = user.partner_id
    request = _request(user)
    _env()._gc_portal_users()
    request.invalidate_recordset()
    assert request.state == 'done'
    assert request.user_int == user.pk
    assert not ResUsers.objects.filter(pk=user.pk).exists()
    assert not ResPartner.objects.filter(pk=partner_id).exists()


def test_batch_size_limits_how_many_are_processed():
    """``todo_requests[:batch_size]`` (``:57``)."""
    first = _request(_user('gc-batch-1@kaupamex.test'))
    second = _request(_user('gc-batch-2@kaupamex.test'))
    _env()._gc_portal_users(batch_size=1)
    first.invalidate_recordset()
    second.invalidate_recordset()
    assert sorted([first.state, second.state]) == ['done', 'todo']


def test_a_failed_user_deletion_marks_the_request_failed(monkeypatch):
    """``delete_request.state = "fail"`` (``:76-84``)."""
    user = _user('gc-fail@kaupamex.test')
    request = _request(user)

    def refuse(self, *args, **kwargs):
        raise RuntimeError('refused')

    monkeypatch.setattr(ResUsers, 'delete', refuse)
    _env()._gc_portal_users()
    request.invalidate_recordset()
    assert request.state == 'fail'
    assert ResUsers.objects.filter(pk=user.pk).exists()


def test_an_internal_user_cannot_read_requests():
    """ACL nula para todos (``ir.model.access.csv:87``)."""
    user = _user('gc-acl@kaupamex.test')
    _request(user)
    with user_scope(user.pk), pytest.raises(AccessError):
        Environment(uid=user.pk)['res.users.deletion'].search([])
    assert ResUsersDeletion.objects.filter(user_int=user.pk).exists()


def test_the_cron_is_seeded():
    """``ir_cron_res_users_deletion`` (``ir_cron_data.xml:13-21``)."""
    from_xmlid = IrModelData._xmlid_to_res_id(
        'base.ir_cron_res_users_deletion', raise_if_not_found=True)
    cron = IrCron.objects.get(pk=from_xmlid)
    assert cron.priority == 8
    assert cron.ir_actions_server.code == (
        'model._gc_portal_users(batch_size=50)')
