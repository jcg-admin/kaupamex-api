"""
Introspección SQL (SOL-091) — tools.sql contra PostgreSQL real (==
odoo.tools.sql).

Usa ``django_migrations`` (siempre presente en la base de test) como sujeto.
"""

import pytest
from django.db import connection

from tools import sql

pytestmark = pytest.mark.django_db


def test_table_exists():
    with connection.cursor() as c:
        assert sql.table_exists(c, 'django_migrations') is True
        assert sql.table_exists(c, 'tabla_que_no_existe') is False


def test_table_exists_counts_views_and_materialized_views():
    """≙ ``table_exists`` (``odoo19c: odoo/tools/sql.py:216-218``), que es
    ``existing_tables`` con ``relkind IN ('r', 'v', 'm')``: un modelo servido
    por una vista materializada TIENE su relación.
    ``information_schema.tables``
    no lista las materializadas, y con él esta pregunta daba ``False``."""
    with connection.cursor() as c:
        c.execute('CREATE VIEW probe_exists_view AS SELECT 1 AS x')
        c.execute('CREATE MATERIALIZED VIEW probe_exists_mat AS SELECT 1 AS x')
        assert sql.table_exists(c, 'probe_exists_view') is True
        assert sql.table_exists(c, 'probe_exists_mat') is True


def test_column_exists():
    with connection.cursor() as c:
        assert sql.column_exists(c, 'django_migrations', 'app') is True
        assert (
            sql.column_exists(c, 'django_migrations', 'columna_inexistente')
            is False
        )


def test_index_exists():
    with connection.cursor() as c:
        # La PK de django_migrations se llama 'PRIMARY' en MariaDB.
        # PostgreSQL nombra el índice de la PK ``<tabla>_pkey``; ``PRIMARY``
        # era el nombre fijo que MariaDB le daba a todas.
        # Firma de la fuente (``odoo19c: odoo/tools/sql.py:540``): el nombre
        # del índice basta, es único dentro del schema.
        assert sql.index_exists(c, 'django_migrations_pkey') is True
        assert sql.index_exists(c, 'idx_inexistente') is False
