"""El cron ejecuta su acción de servidor, como la fuente.

≙ ``_callback`` (``odoo19c: odoo/addons/base/models/ir_cron.py:671-696``):
``self.env['ir.actions.server'].browse(server_action_id).run()`` bajo el
entorno del job. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/cron-runs-server-action.md``.

Qué haría fallar a estos casos: con el corredor de métodos de antes,
``_callback`` llama ``getattr(model, method_name)()`` e ignora ``code``; cada
caso afirma un efecto que sólo el ``code`` produce.

*Métrica:* filas escritas por el código y el ``code`` de las acciones.
*Ciega a:* el bucle de progreso por lotes de ``_run_job``, que no se porta.
"""
import importlib

import pytest
from django.apps import apps

from addons.base.data.cron import sembrar_cron_vivo
from addons.base.models import IrActionsServer, IrCron
from addons.base.models.res_partner import ResPartner
from orm.environments import sudo

pytestmark = pytest.mark.django_db

PARTNER = 'base.ResPartner'


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


def _cron(code, method_name=''):
    action = IrActionsServer.objects.create(
        name='Cron de prueba', state='code', model_name=PARTNER,
        method_name=method_name, code=code)
    return IrCron.objects.create(ir_actions_server=action,
                                 interval_number=1, interval_type='days')


def test_the_cron_runs_the_code_of_its_action():
    partner = ResPartner.objects.create(name='Antes')
    cron = _cron(f"env['res.partner'].browse({partner.pk})"
                 ".write({'name': 'Despues'})")
    cron._callback()
    partner.refresh_from_db()
    assert partner.name == 'Despues'


def test_the_code_sees_the_cron_id_in_the_context():
    cron = _cron("model.objects.create(name='cron %s' "
                 "% env.context['cron_id'])")
    cron._callback()
    assert ResPartner.objects.filter(name=f'cron {cron.pk}').exists()


def test_a_seeded_action_without_code_calls_its_method():
    spec = {'name': 'Sin code', 'model_name': PARTNER,
            'method_name': '_cron_probe_method', 'interval_number': 1,
            'interval_type': 'days', 'priority': 5}
    cron, _ = sembrar_cron_vivo(spec)
    assert cron.ir_actions_server.code == 'model._cron_probe_method()'


def test_a_seeded_action_keeps_the_code_of_its_spec():
    spec = {'name': 'Con code', 'model_name': PARTNER,
            'method_name': '_cron_probe_method', 'interval_number': 1,
            'interval_type': 'days', 'priority': 5,
            'code': 'model._cron_probe_method(job_count=3)'}
    cron, _ = sembrar_cron_vivo(spec)
    assert cron.ir_actions_server.code == (
        'model._cron_probe_method(job_count=3)')


def test_the_migration_fills_empty_code_and_keeps_written_code():
    empty = _cron('', method_name='_cron_probe_method').ir_actions_server
    written = _cron('model._other()',
                    method_name='_cron_probe_other').ir_actions_server
    migration = importlib.import_module(
        'addons.base.migrations.0126_fill_cron_action_code')
    migration.fill_code(apps, None)
    empty.refresh_from_db()
    written.refresh_from_db()
    assert empty.code == 'model._cron_probe_method()'
    assert written.code == 'model._other()'
