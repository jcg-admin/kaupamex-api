"""``_check_removed_columns``, ``_add_sql_constraints`` y ``_auto_init``.

≙ ``odoo19c: odoo/orm/models.py:3109-3136, 3170-3248, 3262-3268``
(``abe4040ec1``). Se portan como conciliación tras ``migrate``: cada paso
comprueba antes de actuar, así que sobre un esquema sincronizado no emite
nada. Diseño: ``designs/schema-and-translation-symbols-decision.md``,
revisión «los tres símbolos se portan con su contrato» (s1-s4).
"""
import pytest
from django.db import connection

from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

TABLE = 'test_orm_category'


@pytest.fixture
def env(db, system_user):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def _nullable(column):
    with connection.cursor() as cr:
        cr.execute(
            'SELECT is_nullable FROM information_schema.columns '
            'WHERE table_name = %s AND column_name = %s', [TABLE, column])
        return cr.fetchone()[0]


def _orphan_column():
    """Una columna ``NOT NULL`` que el modelo no declara — la que deja un
    campo retirado o un módulo que la añadía."""
    with connection.cursor() as cr:
        cr.execute(f'ALTER TABLE {TABLE} ADD COLUMN orphan_flag integer '
                   'NOT NULL DEFAULT 0')


def test_an_orphan_column_loses_its_not_null(env):
    _orphan_column()
    assert _nullable('orphan_flag') == 'NO'
    env['test_orm.category']._check_removed_columns()
    assert _nullable('orphan_flag') == 'YES'


def test_a_declared_column_keeps_its_not_null(env):
    _orphan_column()
    env['test_orm.category']._check_removed_columns()
    assert _nullable('name') == 'NO'
    assert _nullable('id') == 'NO'
