"""``res.device`` y ``res.device.log`` sobre ``models.BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/res_device.py:17-19,92-113,120-128,
143-169,185-196``. Con la ACL aplicada (``group_user`` sólo lee,
``odoo19c: odoo/addons/base/security/ir.model.access.csv:145-146``), los
escritores del log corren elevados, como el SQL crudo y el ``sudo()`` de la
fuente. Diseño: ``designs/basemodel-adoption-res-device.md`` (segundo paso).
"""

import datetime

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.utils import timezone

from addons.base.models.res_device import ResDeviceLog
from addons.base.models.res_users import ResUsers
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

UA = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
)


def _user(login):
    with sudo():
        return ResUsers.objects.create_user(login=login, password='x')


def _log(user, key, last_activity=None):
    with sudo():
        return ResDeviceLog.objects.create(
            session_identifier=key,
            platform='linux',
            browser='chrome',
            ip_address='203.0.113.7',
            user_id=user.pk,
            revoked=False,
            last_activity=last_activity or timezone.now(),
        )


def _session():
    store = SessionStore()
    store['algo'] = 1
    store.create()
    return store


def test_an_internal_user_cannot_write_the_log_directly():
    user = _user('dev-bm-write@kaupamex.test')
    row = _log(user, 'bm-write')
    with user_scope(user.pk), pytest.raises(AccessError):
        row.write({'revoked': True})


def test_update_device_inserts_for_a_plain_user():
    user = _user('dev-bm-update@kaupamex.test')
    request = RequestFactory().get(
        '/', HTTP_USER_AGENT=UA, REMOTE_ADDR='203.0.113.9')
    request.session = _session()
    request.user = user
    with user_scope(user.pk):
        row = ResDeviceLog._update_device(request)
    assert row is not None
    with sudo():
        assert ResDeviceLog.objects.filter(pk=row.pk, user=user).exists()


def test_gc_deletes_for_a_plain_user():
    user = _user('dev-bm-gc@kaupamex.test')
    old = _log(user, 'bm-gc',
               last_activity=timezone.now() - datetime.timedelta(days=1))
    new = _log(user, 'bm-gc')
    with user_scope(user.pk):
        ResDeviceLog._gc_device_log()
    with sudo():
        alive = set(ResDeviceLog.objects.filter(
            session_identifier='bm-gc').values_list('pk', flat=True))
    assert alive == {new.pk}
    assert old.pk not in alive


def test_an_internal_user_reads_only_their_own_logs():
    mine = _user('dev-bm-mine@kaupamex.test')
    other = _user('dev-bm-other@kaupamex.test')
    own = _log(mine, 'bm-read-mine')
    _log(other, 'bm-read-other')
    with user_scope(mine.pk):
        found = Environment(uid=mine.pk)['res.device.log'].search(
            [('session_identifier', 'like', 'bm-read-')])
    assert found.ids == [own.pk]
