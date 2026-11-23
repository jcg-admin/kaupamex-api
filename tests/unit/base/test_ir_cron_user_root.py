"""El cron corre con su usuario, que al instalar es ``base.user_root``.

≙ ``odoo19c: odoo/addons/base/models/ir_cron.py:110`` (``user_id``
obligatorio, por defecto ``self.env.user``) y
``odoo19c: odoo/modules/loading.py:404`` (la instalación carga con
``SUPERUSER_ID``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/ir-cron-user-root.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrActionsServer, IrModelData
from addons.base.models.ir_cron import IrCron
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


def _root_id():
    return IrModelData.objects.get(module='base', name='user_root').res_id


def _action():
    return IrActionsServer.objects.create(
        name='probe', model_name='ir.cron', method_name='_noop',
        state='code', code='')


def test_no_seeded_cron_runs_without_a_user():
    assert IrCron.objects.exists()
    assert not IrCron.objects.filter(user__isnull=True).exists()
    assert set(IrCron.objects.values_list('user_id', flat=True)) == {
        _root_id()}


def test_the_user_column_is_required():
    assert IrCron._meta.get_field('user').null is False


def test_without_a_user_the_default_is_the_root():
    cron = IrCron.objects.create(ir_actions_server=_action(),
                                 interval_number=1, interval_type='days')
    assert cron.user_id == _root_id()


def test_under_a_user_the_default_is_that_user():
    with sudo():
        user = get_user_model().objects.create_user(
            login='cron-default-user', password=None, name='cron')
    with user_scope(user.pk):
        cron = IrCron.objects.create(ir_actions_server=_action(),
                                     interval_number=1, interval_type='days')
    assert cron.user_id == user.pk
