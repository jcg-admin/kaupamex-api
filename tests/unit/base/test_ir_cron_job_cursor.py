"""Cada trabajo del cron corre en su propio cursor (RED de la unidad
``registry-cursor-unit-of-work-0485``, consumidor real).

≙ ``IrCron._run_job``
(``odoo19c: odoo/addons/base/models/ir_cron.py:480-486``):
``with cls.pool.cursor() as job_cr:`` y ``api.Environment(job_cr,
job['user_id'], {...})``. El volcado de lo que un trabajo deja pendiente
ocurre en el COMMIT de SU cursor y como SU usuario. Hoy el trabajo corre con
``user_scope`` sobre la conexión del planificador: lo pendiente lo vuelca el
COMMIT del planificador como el ``default_env`` que haya en esa conexión.
"""
from datetime import timedelta

import pytest
from django.apps import apps
from django.utils import timezone

from addons.base.models import IrActionsServer, IrCron, SystemParameter
from orm.environments import env, get_transaction
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db

SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')


@pytest.fixture(autouse=True)
def _only_our_crons(db):
    IrCron.objects.all().delete()


def _cron(user, method_name):
    action = IrActionsServer.objects.create(
        name=method_name, model_name='base.SystemParameter',
        method_name=method_name, state='code', path=None)
    return IrCron.objects.create(
        ir_actions_server=action, user=user, priority=5,
        nextcall=timezone.now() - timedelta(minutes=5))


def test_a_job_flushes_its_pending_writes_as_its_own_user(monkeypatch):
    first_user, second_user = UserFactory(), UserFactory()
    created = []

    def fix_an_environment(cls):
        # el primer trabajo construye un entorno con su usuario, que en la
        # conexión compartida se queda como ``default_env``
        env()(user=first_user.pk)

    def leave_a_pending_compute(cls):
        record = env()['test_orm.shared.compute'].sudo().create(
            {'name': '2->5'})
        record.name = '3->6'         # recálculo pendiente de volcar
        created.append(record.id)

    monkeypatch.setattr(SystemParameter, 'fix_an_environment',
                        classmethod(fix_an_environment), raising=False)
    monkeypatch.setattr(SystemParameter, 'leave_a_pending_compute',
                        classmethod(leave_a_pending_compute), raising=False)
    _cron(first_user, 'fix_an_environment')
    _cron(second_user, 'leave_a_pending_compute')

    IrCron._process_jobs()
    # lo que el planificador confirmaría al terminar su ciclo
    get_transaction().flush()

    row = SharedCompute.objects.values('start', 'end', 'write_uid').get(
        pk=created[0])
    assert row == {'start': 3, 'end': 6, 'write_uid': second_user.pk}
