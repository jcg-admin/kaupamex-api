"""Introspección SQL (SOL-091) — tools.sql contra PostgreSQL real (== odoo.tools.sql).

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
    # ``schema`` designa un NAMESPACE dentro de la base, no otra base: el
    # explícito es ``public``, no ``settings_dict['NAME']`` como bajo MariaDB.
    with connection.cursor() as c:
        assert sql.table_exists(c, 'django_migrations', schema='public') is True
        assert sql.table_exists(c, 'django_migrations', schema='information_schema') is False


def test_column_exists():
    with connection.cursor() as c:
        assert sql.column_exists(c, 'django_migrations', 'app') is True
        assert sql.column_exists(c, 'django_migrations', 'columna_inexistente') is False


def test_index_exists():
    with connection.cursor() as c:
        # La PK de django_migrations se llama 'PRIMARY' en MariaDB.
        # PostgreSQL nombra el índice de la PK ``<tabla>_pkey``; ``PRIMARY``
        # era el nombre fijo que MariaDB le daba a todas.
        assert sql.index_exists(c, 'django_migrations', 'django_migrations_pkey') is True
        assert sql.index_exists(c, 'django_migrations', 'idx_inexistente') is False
