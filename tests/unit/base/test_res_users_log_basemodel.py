"""``res.users.log`` sobre ``models.BaseModel``, con ``create_uid`` dueño.

≙ ``odoo19c: odoo/addons/base/models/res_users.py:134-152,231,742-746``,
``odoo/addons/base/security/ir.model.access.csv:89`` y
``base_security.xml:5-10``. Diseño:
``designs/basemodel-adoption-res-users-log.md``.
"""

import pytest

from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers, ResUsersLog
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _user(login):
    with sudo():
        partner = ResPartner.objects.create(name=login, email='')
        return ResUsers.objects.create(login=login, partner=partner)


def test_the_login_row_belongs_to_the_user_by_create_uid():
    """``_update_last_login`` (``:742-746``) estampa el ``create_uid``."""
    user = _user('log-owner@kaupamex.test')
    user._update_last_login()
    row = ResUsersLog.objects.get(create_uid=user)
    assert row.create_uid_id == user.pk


def test_the_inverse_is_log_ids():
    """``res.users.log_ids`` (``:231``)."""
    user = _user('log-inverse@kaupamex.test')
    user._update_last_login()
    assert user.log_ids.count() == 1


def test_an_internal_user_cannot_read_the_log():
    """ACL de ``group_system`` (``ir.model.access.csv:89``)."""
    user = _user('log-acl@kaupamex.test')
    user._update_last_login()
    with user_scope(user.pk), pytest.raises(AccessError):
        Environment(uid=user.pk)['res.users.log'].search([])
