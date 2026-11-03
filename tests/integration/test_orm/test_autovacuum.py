"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_autovacuum.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1``.

**Adaptación declarada:** la fuente dispara el cron ``base.autovacuum_job``
con ``method_direct_trigger`` dentro del modo de prueba del registro; aquí se
invoca su método, ``IrAutovacuum._run_vacuum_cleaner``, con el ``cron_id``
en el contexto, que es lo que el cron le entrega (``ir_cron.py:_callback``).
"""

from datetime import datetime, timedelta

import pytest

from addons.base.models.ir_actions import IrActionsServerHistory
from addons.base.models.ir_autovacuum import IrAutovacuum, _call_vacuum_method
from orm.environments import context_scope

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_api_autovacuum(env):
    Model = env['test_orm.autovacuumed']
    instance = Model.create({'expire_at': datetime.now() - timedelta(days=15)})
    assert instance.exists()

    with context_scope(cron_id=1):
        IrAutovacuum._run_vacuum_cleaner()

    assert not instance.exists()


@pytest.mark.django_db
def test_an_instance_method_of_a_plain_model_runs_from_the_sweep():
    """Caso propio del Consumer: ``_gc_histories`` es un método de instancia
    ``@autovacuum`` sobre un modelo que no deriva de ``BaseModel``. El barrido
    lo llamaba sin argumento y levantaba ``TypeError``, así que nunca corría.
    """
    _call_vacuum_method(
        IrActionsServerHistory, IrActionsServerHistory._gc_histories)
