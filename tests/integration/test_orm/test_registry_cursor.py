"""``Registry.cursor()`` abre una unidad de trabajo con conexión y
transacción del ORM propias.

≙ ``Registry.cursor`` (``odoo19c: odoo/orm/registry.py:1165-1186``) y el
ciclo de ``BaseCursor`` (``odoo/sql_db.py:228-245``, ``:524-576``): el cursor
es nuevo, ``with cr:`` confirma si no hubo excepción y cierra siempre, y la
transacción del ORM —con su ``default_env``— muere con él. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
registry-cursor-unit-of-work.md``.

Las filas que un cursor confirma quedan fuera de la transacción de la prueba,
así que cada prueba las retira con otro cursor al terminar.
"""
import pytest
from django.apps import apps
from django.db import connections, transaction

from orm import registry as orm_registry
from orm.environments import Environment, _connection_transaction
from orm.utils import SUPERUSER_ID
from tests.conftest import REAL_REGISTRY_CURSOR
from tests.cursor_support import TestCursor

SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')


@pytest.fixture(autouse=True)
def _unblocked(django_db_setup, django_db_blocker):
    """El cursor real abre su propia conexión, que un ``TestCase`` rechaza:
    estas pruebas corren fuera de él, como el alias de sondeo de
    ``test_env_alias_recordset``."""
    with django_db_blocker.unblock():
        yield


class _Real:
    """``Registry('default')`` con el ``cursor`` del núcleo, no el de
    pruebas."""

    def cursor(self, readonly=False):
        return REAL_REGISTRY_CURSOR(orm_registry.Registry('default'),
                                    readonly)


def _registry():
    return _Real()


def _committed(pk):
    """La fila vista desde una conexión que sólo ve lo confirmado."""
    with _registry().cursor() as cr:
        cr.execute('SELECT name, write_uid FROM test_orm_shared_compute '
                   'WHERE id = %s', [pk])
        return cr.fetchone()


def _purge(*pks):
    with _registry().cursor() as cr:
        cr.execute('DELETE FROM test_orm_shared_compute WHERE id = ANY(%s)',
                   [list(pks)])


def test_the_cursor_owns_a_connection_of_its_own():
    cr = _registry().cursor()
    try:
        assert cr.alias != 'default'
        assert cr.alias in connections
        env = Environment(cr.alias, SUPERUSER_ID, {})
        assert env.transaction is _connection_transaction(cr.alias)
        assert env.transaction is not _connection_transaction('default')
    finally:
        cr.close()
    assert cr.alias not in connections


def test_with_commits_its_work_and_closes():
    with _registry().cursor() as cr:
        record = Environment(cr.alias, SUPERUSER_ID, {})[
            'test_orm.shared.compute'].create({'name': '2->3'})
        alias = cr.alias
    try:
        assert alias not in connections
        assert _committed(record.id)[0] == '2->3'
    finally:
        _purge(record.id)


def test_an_exception_rolls_back_and_discards_the_transaction():
    created = []
    with pytest.raises(RuntimeError):
        with _registry().cursor() as cr:
            record = Environment(cr.alias, SUPERUSER_ID, {})[
                'test_orm.shared.compute'].create({'name': '4->5'})
            created.append(record.id)
            raise RuntimeError('deshacer')
    assert _committed(created[0]) is None


def test_each_unit_of_work_flushes_as_its_own_user():
    """La fuga de ``default_env`` fuera de pytest: dos unidades seguidas.

    La primera fija ``default_env`` con un usuario que la base no tiene; la
    segunda escribe con el super-usuario. En la fuente cada una tiene su
    cursor (``ir_cron.py:480-486``), así que el volcado de la segunda fecha
    ``write_uid`` con el suyo; si heredara el ``default_env`` de la primera,
    el COMMIT violaría la clave foránea de ``write_uid``.
    """
    with _registry().cursor() as cr:
        Environment(cr.alias, 987654, {})
    with _registry().cursor() as cr:
        env = Environment(cr.alias, SUPERUSER_ID, {})
        record = env['test_orm.shared.compute'].create({'name': '6->7'})
        assert _connection_transaction(cr.alias).default_env is env
    try:
        assert _committed(record.id) == ('6->7', SUPERUSER_ID)
    finally:
        _purge(record.id)


def test_the_cursor_commit_does_not_commit_the_caller():
    """El COMMIT del cursor es de su conexión: lo del llamador sigue sin
    confirmar mientras la transacción de la prueba siga abierta."""
    with transaction.atomic(using='default'):
        outer = SharedCompute.objects.using('default').create(name='8->9')
        with _registry().cursor() as cr:
            inner = Environment(cr.alias, SUPERUSER_ID, {})[
                'test_orm.shared.compute'].create({'name': '1->9'})
        try:
            assert _committed(outer.pk) is None
            assert _committed(inner.id)[0] == '1->9'
        finally:
            _purge(inner.id)
        transaction.set_rollback(True, using='default')


@pytest.mark.django_db
class TestTheTestModeCursor:
    """≙ ``TestCursor`` (``odoo/tests/test_cursor.py``), instalado por
    ``tests/conftest.py`` como ``common.py:800-806`` de la fuente."""

    def test_registry_cursor_is_a_test_cursor_during_a_test(self):
        cr = orm_registry.Registry('default').cursor()
        try:
            assert isinstance(cr, TestCursor)
        finally:
            cr.close()

    def test_each_test_cursor_has_its_own_orm_transaction(self):
        outer = _connection_transaction('default')
        Environment('default', SUPERUSER_ID, {})
        with orm_registry.Registry('default').cursor() as cr:
            Environment(cr.alias, 987654, {})
            inner = _connection_transaction(cr.alias)
            assert inner is not outer
            assert inner.default_env._uid_override == 987654
        assert _connection_transaction('default') is outer
        assert outer.default_env is None or (
            outer.default_env._uid_override != 987654)

    def test_a_rolled_back_unit_leaves_no_row(self):
        with pytest.raises(RuntimeError):
            with orm_registry.Registry('default').cursor() as cr:
                record = Environment(cr.alias, SUPERUSER_ID, {})[
                    'test_orm.shared.compute'].create({'name': '3->4'})
                pk = record.id
                raise RuntimeError('deshacer')
        assert not SharedCompute.objects.filter(pk=pk).exists()
