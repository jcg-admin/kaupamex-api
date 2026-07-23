"""Introspección SQL (SOL-091) — tools.sql contra MariaDB real (== odoo.tools.sql).

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


def test_table_exists_with_explicit_schema():
    name = connection.settings_dict['NAME']
    with connection.cursor() as c:
        assert sql.table_exists(c, 'django_migrations', schema=name) is True
        assert sql.table_exists(c, 'django_migrations', schema='information_schema') is False


def test_column_exists():
    with connection.cursor() as c:
        assert sql.column_exists(c, 'django_migrations', 'app') is True
        assert sql.column_exists(c, 'django_migrations', 'columna_inexistente') is False


def test_index_exists():
    with connection.cursor() as c:
        # La PK de django_migrations se llama 'PRIMARY' en MariaDB.
        assert sql.index_exists(c, 'django_migrations', 'PRIMARY') is True
        assert sql.index_exists(c, 'django_migrations', 'idx_inexistente') is False
