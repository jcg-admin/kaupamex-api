"""El DDL de columna de ``tools/sql.py`` — tarea #211, eje de esquema.

Porta las siete funciones que ``Field.update_db`` y su familia consumen
(``odoo19c: odoo/tools/sql.py``): ``create_column`` (``:337``),
``convert_column`` (``:359``), ``_convert_column`` (``:374``),
``drop_depending_views`` (``:389``), ``get_depending_views`` (``:400``),
``set_not_null`` (``:481``) y ``drop_not_null`` (``:491``).

Los casos corren contra PostgreSQL real sobre una tabla que el propio caso
crea: pytest envuelve cada uno en una transaccion, asi que el DDL se revierte
y ninguna tabla del esquema queda tocada.

**El control que discrimina** es ``test_convert_column_drops_the_view_that_blocks_it``:
sin ``drop_depending_views``, PostgreSQL rechaza el ``ALTER COLUMN ... TYPE``
de una columna que una vista consume, y el caso cae. Un
``convert_column`` que no supiera retirar la vista pasaria el resto de los
casos igual.
"""
import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError

from tools.sql import (convert_column, create_column, drop_depending_views,
                       drop_not_null, get_depending_views, rename_column,
                       set_not_null, table_columns)

TABLE = 'orm_sql_column_probe'


@pytest.fixture
def cursor(db):
    """Un cursor sobre una tabla vacia, creada y revertida por el caso."""
    with connection.cursor() as cur:
        cur.execute(f'CREATE TABLE {TABLE} (id serial PRIMARY KEY)')
        yield cur


def _column(cursor, name):
    return table_columns(cursor, TABLE)[name]


class TestCreateColumn:

    def test_adds_the_column_with_the_given_type(self, cursor):
        create_column(cursor, TABLE, 'label', 'varchar')
        assert _column(cursor, 'label')['udt_name'] == 'varchar'

    def test_a_boolean_column_is_born_with_a_false_default(self, cursor):
        create_column(cursor, TABLE, 'flag', 'boolean')
        cursor.execute(f'INSERT INTO {TABLE} DEFAULT VALUES RETURNING flag')
        assert cursor.fetchone()[0] is False

    def test_the_comment_lands_on_the_column(self, cursor):
        create_column(cursor, TABLE, 'label', 'varchar', 'La etiqueta')
        cursor.execute(
            "SELECT col_description(%s::regclass, ordinal_position) "
            "FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'label'",
            [TABLE, TABLE])
        assert cursor.fetchone()[0] == 'La etiqueta'


class TestConvertColumn:

    def test_changes_the_column_type(self, cursor):
        create_column(cursor, TABLE, 'amount', 'varchar')
        cursor.execute(f"INSERT INTO {TABLE} (amount) VALUES ('12')")
        convert_column(cursor, TABLE, 'amount', 'int4')
        assert _column(cursor, 'amount')['udt_name'] == 'int4'
        cursor.execute(f'SELECT amount FROM {TABLE}')
        assert cursor.fetchone()[0] == 12

    def test_convert_column_drops_the_view_that_blocks_it(self, cursor):
        """El control: sin retirar la vista, PostgreSQL rechaza el ALTER."""
        create_column(cursor, TABLE, 'amount', 'varchar')
        cursor.execute(f'CREATE VIEW {TABLE}_v AS SELECT amount FROM {TABLE}')
        convert_column(cursor, TABLE, 'amount', 'int4')
        assert _column(cursor, 'amount')['udt_name'] == 'int4'
        assert get_depending_views(cursor, TABLE, 'amount') == []


class TestDependingViews:

    def test_lists_the_view_that_reads_the_column(self, cursor):
        create_column(cursor, TABLE, 'amount', 'varchar')
        cursor.execute(f'CREATE VIEW {TABLE}_v AS SELECT amount FROM {TABLE}')
        assert get_depending_views(cursor, TABLE, 'amount') == [
            (f'{TABLE}_v', 'v')]

    def test_a_column_nobody_reads_has_no_view(self, cursor):
        create_column(cursor, TABLE, 'amount', 'varchar')
        assert get_depending_views(cursor, TABLE, 'amount') == []

    def test_drop_removes_the_materialized_view_too(self, cursor):
        create_column(cursor, TABLE, 'amount', 'varchar')
        cursor.execute(
            f'CREATE MATERIALIZED VIEW {TABLE}_m AS SELECT amount FROM {TABLE}')
        assert get_depending_views(cursor, TABLE, 'amount') == [
            (f'{TABLE}_m', 'm')]
        drop_depending_views(cursor, TABLE, 'amount')
        assert get_depending_views(cursor, TABLE, 'amount') == []


class TestNotNull:

    def test_set_adds_the_constraint(self, cursor):
        create_column(cursor, TABLE, 'label', 'varchar')
        assert _column(cursor, 'label')['is_nullable'] == 'YES'
        set_not_null(cursor, TABLE, 'label')
        assert _column(cursor, 'label')['is_nullable'] == 'NO'

    def test_drop_removes_the_constraint(self, cursor):
        create_column(cursor, TABLE, 'label', 'varchar')
        set_not_null(cursor, TABLE, 'label')
        drop_not_null(cursor, TABLE, 'label')
        assert _column(cursor, 'label')['is_nullable'] == 'YES'

    def test_set_refuses_over_an_existing_null(self, cursor):
        """El punto de guardado aisla el rechazo: sin el, la transaccion queda
        abortada y el resto del caso —y el desmontaje— fallarian por eso y no
        por lo que se mide."""
        create_column(cursor, TABLE, 'label', 'varchar')
        cursor.execute(f'INSERT INTO {TABLE} DEFAULT VALUES')
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                set_not_null(cursor, TABLE, 'label')
        assert _column(cursor, 'label')['is_nullable'] == 'YES'


class TestRenameColumn:

    def test_the_column_answers_by_its_new_name(self, cursor):
        create_column(cursor, TABLE, 'label', 'varchar')
        rename_column(cursor, TABLE, 'label', 'title')
        columnas = table_columns(cursor, TABLE)
        assert 'label' not in columnas
        assert columnas['title']['udt_name'] == 'varchar'
