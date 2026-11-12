"""Extensión de las pruebas de propiedad del entorno (§4 del diseño
``designs/environment-ownership-contract.md``).

Borrador: se mueve a ``tests/integration/test_orm/`` después de integrar el
lote verificado, con su RED medido por anulación de cada guarda.

Los ids coincidentes entre dos bases no se pueden ensayar sobre el alias de
sondeo —comparte la base con ``default`` y un INSERT con la misma clave
esperaría el bloqueo de la otra conexión—; los cubre
``test_multidb_isolation.TestStoredComputesStayInTheirBase`` en ci-multidb.
"""
from unittest import mock

import pytest
from django.apps import apps
from django.db import connections

from orm import models as orm_models
from orm.environments import (Environment, _connection_transaction,
                              get_current_cr)
from orm.utils import SUPERUSER_ID
from service.db import savepoint
from tests.integration.test_orm import test_env_alias_recordset as alias_probe

SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')
probe_alias = alias_probe.probe_alias


def _pending(alias):
    return {record_id
            for field, ids in _connection_transaction(alias).tocompute.items()
            if getattr(field, 'model', None) is SharedCompute
            for record_id in ids}


def _row(alias, pk):
    return SharedCompute.objects.using(alias).values(
        'start', 'end').get(pk=pk)


def test_a_nested_flush_restores_the_enclosing_environment(probe_alias):
    """El ``with`` de ``flush_all`` devuelve el canal al entorno de fuera."""
    with Environment('default', SUPERUSER_ID, {}):
        Environment(probe_alias, SUPERUSER_ID, {}).flush_all()
        assert get_current_cr() == 'default'
    assert get_current_cr() is None


def test_a_failing_flush_restores_the_enclosing_environment(probe_alias):
    """Con excepción dentro del volcado, el canal vuelve igual."""
    SharedCompute.objects.using(probe_alias).create(name='2->3')
    boom = RuntimeError('fallo de escritura')
    with mock.patch.object(orm_models, '_write_rows', side_effect=boom):
        with pytest.raises(RuntimeError):
            Environment(probe_alias, SUPERUSER_ID, {}).flush_all()
    assert get_current_cr() is None


def test_flushing_one_base_keeps_the_marks_of_the_other(probe_alias):
    """Volcar el alias no consume ni ejecuta las marcas de ``default``."""
    mine = SharedCompute.objects.using(probe_alias).create(name='1->5')
    theirs = SharedCompute.objects.using('default').create(name='2->6')
    assert theirs.pk in _pending('default')
    Environment(probe_alias, SUPERUSER_ID, {}).flush_all()
    assert _pending(probe_alias) == set()
    assert theirs.pk in _pending('default')
    assert _row(probe_alias, mine.pk) == {'start': 1, 'end': 5}
    Environment('default', SUPERUSER_ID, {}).flush_all()
    assert _row('default', theirs.pk) == {'start': 2, 'end': 6}


def test_each_mark_is_computed_once(probe_alias):
    """Una marca se calcula una vez: el segundo volcado no repite."""
    SharedCompute.objects.using(probe_alias).create(name='4->7')
    env = Environment(probe_alias, SUPERUSER_ID, {})
    model = type(env['test_orm.shared.compute'])
    original = model._compute_start_end if hasattr(
        model, '_compute_start_end') else None
    if original is None:
        pytest.skip('el cómputo de la sonda no se llama _compute_start_end')
    with mock.patch.object(model, '_compute_start_end',
                           autospec=True, side_effect=original) as spy:
        env.flush_all()
        env.flush_all()
    assert spy.call_count == 1


def test_flush_recordset_leaves_the_other_rows_pending(probe_alias):
    """El volcado parcial sólo consume las filas del recordset."""
    first = SharedCompute.objects.using(probe_alias).create(name='1->2')
    second = SharedCompute.objects.using(probe_alias).create(name='3->4')
    records = Environment(probe_alias, SUPERUSER_ID, {})[
        'test_orm.shared.compute']
    records.browse(first.pk).flush_recordset()
    assert first.pk not in _pending(probe_alias)
    assert second.pk in _pending(probe_alias)


def test_a_savepoint_rollback_clears_only_its_own_transaction(probe_alias):
    """El corte del savepoint vacía la transacción de su conexión."""
    SharedCompute.objects.using('default').create(name='5->9')
    pending_default = set(_pending('default'))
    with pytest.raises(RuntimeError):
        with savepoint(connections[probe_alias]):
            SharedCompute.objects.using(probe_alias).create(name='6->9')
            raise RuntimeError('deshacer')
    assert _pending(probe_alias) == set()
    assert _pending('default') == pending_default
