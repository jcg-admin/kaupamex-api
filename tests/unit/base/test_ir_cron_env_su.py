"""El trabajo de un cron corre con la elevación de su usuario.

≙ ``env = api.Environment(job_cr, job['user_id'], …)``
(``odoo19c: odoo/addons/base/models/ir_cron.py:482``) y ``if uid ==
SUPERUSER_ID: su = True`` (``odoo19c: odoo/orm/environments.py:66-67``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
ir-cron-env-su.md``.
"""
import pytest

from addons.base.models import IrActionsServer, IrCron, SystemParameter
from orm.environments import SUPERUSER_ID, is_su, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def seen(monkeypatch):
    observed = {}
    monkeypatch.setattr(
        SystemParameter, 'su_probe',
        classmethod(lambda cls: observed.update(su=is_su())),
        raising=False,
    )
    return observed


def _cron(user=None):
    action = IrActionsServer.objects.create(
        name='su probe', model_name='base.SystemParameter',
        method_name='su_probe', state='code', code='', path=None)
    values = {'ir_actions_server': action}
    if user is not None:
        values['user'] = user
    return IrCron.objects.create(**values)


def test_a_root_cron_runs_elevated(seen):
    cron = _cron()
    assert cron.user_id == SUPERUSER_ID
    cron._callback()
    assert seen['su'] is True


def test_a_user_cron_does_not_inherit_the_caller_elevation(
        seen, django_user_model):
    user = django_user_model.objects.create_user(
        login='cron.su.probe@kaupamex.test', password='x')
    cron = _cron(user)
    with sudo():
        cron._callback()
    assert seen['su'] is False
