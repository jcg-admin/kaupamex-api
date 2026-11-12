"""El marcado de creación vive en la transacción de la base donde cayó la
fila.

≙ ``_create`` (``odoo19c: odoo/orm/models.py:4930-4933``): ``modified(...,
create=True)`` marca en ``self.env``, cuya transacción es la de **su** cursor
(``environments.py:70-72``), y ``_flush`` escribe por ese mismo cursor. Aquí
el cursor es el alias: una fila guardada en el alias B se marca en la
transacción de B y se vuelca por B, nunca por ``default``.

El alias de la prueba apunta a la misma base de pruebas con conexión y
transacción propias (fixture de ``test_env_alias_recordset``): una fila escrita
por esa conexión no existe para ``default`` mientras no se confirme, así que
las aserciones distinguen en qué conexión cayó cada marca y cada escritura.
"""
import pytest
from django.apps import apps

from orm.environments import Environment, _connection_transaction
from orm.utils import SUPERUSER_ID
from tests.integration.test_orm import test_env_alias_recordset as alias_probe

SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')

#: El alias de sondeo de ``test_env_alias_recordset``, registrado aquí como
#: fixture de este módulo.
probe_alias = alias_probe.probe_alias


def _marked(alias):
    return sorted(field.name
                  for field, ids in _connection_transaction(alias)
                  .tocompute.items()
                  if ids and getattr(field, 'model', None) is SharedCompute)


def _row(alias, pk):
    return SharedCompute.objects.using(alias).values(
        'name', 'start', 'end').get(pk=pk)


def test_a_django_creation_is_marked_in_its_own_alias(probe_alias):
    record = SharedCompute.objects.using(probe_alias).create(name='5->25')
    assert _marked('default') == []
    assert _marked(probe_alias) == ['end', 'start']
    with Environment(probe_alias, SUPERUSER_ID, {}) as env:
        env.flush_all()
    assert _row(probe_alias, record.pk) == {'name': '5->25', 'start': 5,
                                            'end': 25}
    assert not SharedCompute.objects.using('default').filter(
        pk=record.pk).exists()


def test_an_orm_creation_is_marked_in_its_own_alias(probe_alias):
    with Environment(probe_alias, SUPERUSER_ID, {}) as env:
        record = env['test_orm.shared.compute'].create({'name': '5->25'})
        assert _marked('default') == []
        env.flush_all()
        assert _row(probe_alias, record.id) == {'name': '5->25', 'start': 5,
                                                'end': 25}


def test_an_environment_holds_the_transaction_of_its_own_cursor(probe_alias):
    """≙ ``Environment.__new__`` (``environments.py:70-80``): la
    transacción sale del cursor del entorno, no del bloque que esté abierto.
    Un entorno sobre otro alias, usado sin entrar en él, vuelca y marca en la
    suya."""
    other = Environment(probe_alias, SUPERUSER_ID, {})
    assert other.transaction is _connection_transaction(probe_alias)
    assert other.transaction is not _connection_transaction('default')


def test_a_flush_writes_through_its_own_cursor_without_entering_it(
        probe_alias):
    """``env.flush_all()`` escribe por el cursor de ``env``, esté o no activo.

    ≙ ``_flush`` → ``_write_multi`` sobre ``self.env.cr``
    (``odoo19c: odoo/orm/models.py:4520-4526``). ``init_models`` vuelca el
    entorno de una base sin entrar en él (ci-multidb f77418eb:
    ``CompanyContextRequired`` al leer ``res.partner`` por el enrutador). Si
    la escritura buscara la fila por la base por defecto no la encontraría
    —está sin confirmar en la otra conexión— y la saltaría en silencio.
    """
    record = SharedCompute.objects.using(probe_alias).create(name='6->9')
    Environment(probe_alias, SUPERUSER_ID, {}).flush_all()
    assert _row(probe_alias, record.pk) == {'name': '6->9', 'start': 6,
                                            'end': 9}


def test_write_multi_writes_through_the_cursor_of_its_recordset(probe_alias):
    """``_write_multi`` escribe por ``self.env.cr``, no por el entorno activo.

    ≙ ``odoo19c: odoo/orm/models.py:4520-4526``. El recordset es del alias y
    el entorno activo es ``default``: buscar la fila por el enrutador la
    pediría a ``default``, donde aún no existe, y la escritura se perdería.
    """
    record = SharedCompute.objects.using(probe_alias).create(name='1->2')
    records = Environment(probe_alias, SUPERUSER_ID, {})[
        'test_orm.shared.compute'].browse(record.pk)
    records._write_multi([{'name': '3->4'}])
    assert SharedCompute.objects.using(probe_alias).values_list(
        'name', flat=True).get(pk=record.pk) == '3->4'


def test_flush_model_flushes_the_transaction_of_its_recordset(probe_alias):
    """``flush_model`` vuelca las marcas de ``self.env``, no las del activo.

    ≙ ``BaseModel.flush_model`` → ``_flush`` (``odoo19c:
    odoo/orm/models.py:6353-6400``): sucios, caché y base salen del entorno
    del recordset.
    """
    record = SharedCompute.objects.using(probe_alias).create(name='7->8')
    Environment(probe_alias, SUPERUSER_ID, {})[
        'test_orm.shared.compute'].browse(record.pk).flush_model()
    assert _row(probe_alias, record.pk) == {'name': '7->8', 'start': 7,
                                            'end': 8}
