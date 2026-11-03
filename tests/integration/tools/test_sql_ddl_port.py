"""Las funciones de DDL de ``odoo19c: odoo/tools/sql.py`` que faltaban.

Contra PostgreSQL real: el DDL es transaccional allí, así que cada caso crea
sus tablas dentro de la transacción de la prueba y el rollback las retira.
"""

import pytest
from django.db import connection

from tools import sql

pytestmark = pytest.mark.django_db


def _table(cursor, name, extra=''):
    cursor.execute(f'CREATE TABLE {name} (id serial PRIMARY KEY, code varchar{extra})')


class TestTableKind:
    """≙ ``TableKind`` / ``table_kind`` (``:221-258``)."""

    def test_the_members_carry_the_relkind_letter(self):
        assert [(k.name, k.value) for k in sql.TableKind] == [
            ('Regular', 'r'), ('Temporary', 't'), ('View', 'v'),
            ('Materialized', 'm'), ('Foreign', 'f'), ('Other', None)]

    def test_each_kind_is_told_apart(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_kind_regular')
            cr.execute('CREATE TEMP TABLE probe_kind_temp (id int)')
            cr.execute('CREATE VIEW probe_kind_view AS SELECT 1 AS x')
            cr.execute('CREATE MATERIALIZED VIEW probe_kind_mat AS SELECT 1 AS x')
            cr.execute('CREATE SEQUENCE probe_kind_seq')
            assert sql.table_kind(cr, 'probe_kind_regular') is sql.TableKind.Regular
            assert sql.table_kind(cr, 'probe_kind_view') is sql.TableKind.View
            assert sql.table_kind(cr, 'probe_kind_mat') is sql.TableKind.Materialized
            assert sql.table_kind(cr, 'probe_kind_seq') is sql.TableKind.Other
            assert sql.table_kind(cr, 'probe_kind_missing') is None
            # La consulta de la fuente filtra por ``current_schema``: una tabla
            # temporal vive en ``pg_temp_N`` y no aparece.
            assert sql.table_kind(cr, 'probe_kind_temp') is None

    def test_drop_view_if_exists_drops_views_only(self):
        """≙ ``drop_view_if_exists`` (``:632-637``)."""
        with connection.cursor() as cr:
            _table(cr, 'probe_dv_table')
            cr.execute('CREATE VIEW probe_dv_view AS SELECT 1 AS x')
            cr.execute('CREATE MATERIALIZED VIEW probe_dv_mat AS SELECT 1 AS x')
            for name in ('probe_dv_table', 'probe_dv_view', 'probe_dv_mat', 'probe_dv_none'):
                sql.drop_view_if_exists(cr, name)
            assert sql.table_kind(cr, 'probe_dv_table') is sql.TableKind.Regular
            assert sql.table_kind(cr, 'probe_dv_view') is None
            assert sql.table_kind(cr, 'probe_dv_mat') is None


class TestCreateModelTable:
    """≙ ``create_model_table`` (``:274-296``)."""

    def test_the_table_has_id_columns_and_comments(self):
        with connection.cursor() as cr:
            sql.create_model_table(cr, 'probe_model_table', 'Una tabla',
                                   [('name', 'varchar', 'Nombre')])
            cr.execute("""SELECT obj_description('probe_model_table'::regclass, 'pg_class'),
                                 col_description('probe_model_table'::regclass, 2)""")
            assert cr.fetchone() == ('Una tabla', 'Nombre')
            assert sql.table_columns(cr, 'probe_model_table').keys() >= {'id', 'name'}


class TestConstraints:
    """≙ ``constraint_definition`` / ``add_constraint`` (``:438-463``)."""

    def test_the_definition_is_the_comment(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_constraint')
            sql.add_constraint(cr, 'probe_constraint', 'probe_code_uniq', 'unique(code)')
            assert sql.constraint_definition(
                cr, 'probe_constraint', 'probe_code_uniq') == 'unique(code)'
            assert sql.constraint_definition(cr, 'probe_constraint', 'missing') is None

    def test_a_percent_in_the_definition_survives(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_constraint_pct')
            sql.add_constraint(cr, 'probe_constraint_pct', 'probe_pct_check',
                               "CHECK (code NOT LIKE '%x')")
            assert sql.constraint_definition(
                cr, 'probe_constraint_pct', 'probe_pct_check') == "CHECK (code NOT LIKE '%x')"


class TestFixForeignKey:
    """≙ ``fix_foreign_key`` (``:510-537``)."""

    def test_recreates_only_when_the_policy_differs(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_fk_parent')
            cr.execute('CREATE TABLE probe_fk_child (id serial PRIMARY KEY, parent_id int)')
            assert sql.fix_foreign_key(cr, 'probe_fk_child', 'parent_id',
                                       'probe_fk_parent', 'id', 'cascade') is True
            assert sql.fix_foreign_key(cr, 'probe_fk_child', 'parent_id',
                                       'probe_fk_parent', 'id', 'cascade') is False
            assert sql.fix_foreign_key(cr, 'probe_fk_child', 'parent_id',
                                       'probe_fk_parent', 'id', 'set null') is True
            assert sql.get_foreign_keys(cr, 'probe_fk_child', 'parent_id',
                                        'probe_fk_parent', 'id', 'cascade') == []
            assert len(sql.get_foreign_keys(cr, 'probe_fk_child', 'parent_id',
                                            'probe_fk_parent', 'id', 'set null')) == 1


class TestIndexes:
    """≙ ``index_exists`` … ``create_unique_index`` (``:540-623``)."""

    def test_index_exists_takes_the_name_only(self):
        with connection.cursor() as cr:
            assert sql.index_exists(cr, 'django_migrations_pkey')
            assert not sql.index_exists(cr, 'idx_inexistente')
            sql.check_index_exist(cr, 'django_migrations_pkey')
            with pytest.raises(AssertionError, match='idx_inexistente does not exist'):
                sql.check_index_exist(cr, 'idx_inexistente')

    def test_add_index_with_comment_and_its_definition(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_index')
            sql.add_index(cr, 'probe_index_code', 'probe_index', 'USING btree (code)',
                          unique=True, comment='por codigo')
            definition, comment = sql.index_definition(cr, 'probe_index_code')
            assert definition.startswith('CREATE UNIQUE INDEX probe_index_code')
            assert comment == 'por codigo'
            assert sql.index_definition(cr, 'probe_index_missing') == (None, None)

    def test_create_index_is_unique_on_demand_and_idempotent(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_create_index')
            sql.create_index(cr, 'probe_create_index_code', 'probe_create_index',
                             ['code'], unique=True, comment='c')
            sql.create_index(cr, 'probe_create_index_code', 'probe_create_index', ['code'])
            definition, comment = sql.index_definition(cr, 'probe_create_index_code')
            assert definition.startswith('CREATE UNIQUE INDEX')
            assert comment == 'c'
            with pytest.raises(AssertionError, match='Missing expressions'):
                sql.create_index(cr, 'probe_empty', 'probe_create_index', [])

    def test_create_unique_index_is_deprecated(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_unique_index')
            with pytest.warns(DeprecationWarning, match='create_index'):
                sql.create_unique_index(cr, 'probe_unique_index_code',
                                        'probe_unique_index', ['code'])
            assert sql.index_definition(
                cr, 'probe_unique_index_code')[0].startswith('CREATE UNIQUE INDEX')


class TestTranslatableColumn:
    """≙ ``convert_column_translatable`` (``:361-371``)."""

    def test_round_trip_through_jsonb(self):
        with connection.cursor() as cr:
            _table(cr, 'probe_translatable')
            cr.execute("INSERT INTO probe_translatable (code) VALUES ('hola'), (NULL)")
            sql.convert_column_translatable(cr, 'probe_translatable', 'code', 'jsonb')
            cr.execute('SELECT code FROM probe_translatable ORDER BY id')
            assert [row[0] for row in cr.fetchall()] == ['{"en_US": "hola"}', None]
            sql.convert_column_translatable(cr, 'probe_translatable', 'code', 'varchar')
            cr.execute('SELECT code FROM probe_translatable ORDER BY id')
            assert [row[0] for row in cr.fetchall()] == ['hola', None]


class TestPureHelpers:
    """``reverse_order`` y los patrones de trigramas (``:662-764``)."""

    def test_reverse_order(self):
        assert sql.reverse_order('name, id desc') == 'name desc, id asc'
        assert sql.reverse_order('Date ASC') == 'date desc'

    def test_value_pattern(self):
        assert sql.value_to_translated_trigram_pattern('ab') == '%'
        assert sql.value_to_translated_trigram_pattern('a_b"c%') == r'%a\_b\\"c\%%'

    def test_pattern_pattern(self):
        assert sql.pattern_to_translated_trigram_pattern('ab%') == '%'
        assert sql.pattern_to_translated_trigram_pattern(r'abc%de"f\%g') == r'%abc%de\\"f\%g%'
