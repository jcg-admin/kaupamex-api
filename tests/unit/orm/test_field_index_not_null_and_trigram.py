"""``Field.index`` = ``btree_not_null`` y ``trigram`` en campos ordinarios.

≙ ``Registry.check_indexes`` (``odoo19c: odoo/orm/registry.py:805-892``):
``btree_not_null`` crea un btree sobre la columna con ``WHERE "col" IS NOT
NULL``; ``trigram``, un ``gin`` con ``gin_trgm_ops``. Aquí el esquema lo
llevan las migraciones, así que el índice tiene que llegar al ``Meta`` del
modelo. Diseño en ``designs/field-index-not-null-and-trigram.md`` del
Workbench.

*Métrica:* el SQL que el editor de esquema emite para un modelo sonda, y la
fila de ``pg_indexes`` del portador de la referencia
(``test_orm.message.body``).
*Ciega a:* el ``unaccent`` del índice trigram, que depende de la base y una
migración no conoce (divergencia declarada en el diseño).
"""
import itertools

import pytest
from django.db import connection, models
from django.test.utils import isolate_apps

import fields

pytestmark = pytest.mark.django_db

_PROBES = itertools.count()


def _create_sql(**declared):
    with isolate_apps():
        attrs = {'__module__': __name__,
                 'Meta': type('Meta', (), {'app_label': 'base',
                                           'db_table': 'probe_idx'})}
        attrs.update(declared)
        model = type(f'IndexProbe{next(_PROBES)}', (models.Model,), attrs)
        with connection.schema_editor(collect_sql=True) as editor:
            editor.create_model(model)
    return '\n'.join(editor.collected_sql)


def test_btree_not_null_creates_a_partial_btree_index():
    sql = _create_sql(code=fields.Char(index='btree_not_null'))
    assert 'CREATE INDEX "probe_idx__code_index" ON "probe_idx" ("code")' \
        ' WHERE "code" IS NOT NULL' in sql


def test_trigram_creates_a_gin_trigram_index():
    sql = _create_sql(body=fields.Text(index='trigram'))
    assert 'CREATE INDEX "probe_idx__body_index" ON "probe_idx" USING gin' \
        ' ("body" gin_trgm_ops)' in sql


def test_no_index_value_creates_no_index():
    sql = _create_sql(plain=fields.Char(index=False))
    assert 'CREATE INDEX' not in sql


def test_the_reference_carrier_has_its_trigram_index():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes"
            " WHERE tablename = 'test_orm_message'"
            " AND indexname = 'test_orm_message__body_index'")
        rows = cursor.fetchall()
    assert len(rows) == 1
    assert 'USING gin' in rows[0][0]
    assert 'gin_trgm_ops' in rows[0][0]
