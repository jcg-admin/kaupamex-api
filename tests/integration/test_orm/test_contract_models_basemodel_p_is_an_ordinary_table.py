"""``BaseModel._is_an_ordinary_table`` — ≙ ``odoo19c:
odoo/orm/models.py:596-597``. TASK-API-0485.

La fuente pregunta al registro de su base (``self.pool``): el modelo no
decide por sí mismo si su tabla es ordinaria (``relkind = 'r'``).
"""
import pytest

from orm.registry import Registry

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_is_an_ordinary_table_for_a_real_table(env):
    assert env['test_orm.foo']._is_an_ordinary_table() is True


def test_is_an_ordinary_table_asks_the_registry_of_its_base(env):
    Foo = env['test_orm.foo']
    pool = Registry(env.db_alias)
    pool.is_an_ordinary_table(Foo)
    saved = pool._ordinary_tables
    pool._ordinary_tables = frozenset()
    try:
        assert Foo._is_an_ordinary_table() is False
    finally:
        pool._ordinary_tables = saved
