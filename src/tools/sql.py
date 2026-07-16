"""Introspección SQL sobre ``information_schema`` (fiel a ``odoo.tools.sql``).

``odoo/tools/sql.py`` ofrece ``table_exists``/``column_exists``/``index_exists``
sobre ``information_schema``. Aquí la versión **MariaDB**: el "current schema" de
Odoo (``current_schema`` de PostgreSQL) es ``DATABASE()`` en MariaDB. Todas
reciben un ``cursor`` de Django (``connections[alias].cursor()``) y devuelven bool.
"""


def table_exists(cursor, table_name, schema=None):
    """== ``odoo.tools.sql.table_exists``: ¿existe la tabla?

    ``schema=None`` → el schema de la conexión (``DATABASE()``).
    """
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM information_schema.TABLES '
            'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s',
            [table_name])
    else:
        cursor.execute(
            'SELECT 1 FROM information_schema.TABLES '
            'WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s',
            [schema, table_name])
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name, schema=None):
    """== ``odoo.tools.sql.column_exists``: ¿existe la columna?"""
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM information_schema.COLUMNS '
            'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s',
            [table_name, column_name])
    else:
        cursor.execute(
            'SELECT 1 FROM information_schema.COLUMNS '
            'WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s',
            [schema, table_name, column_name])
    return cursor.fetchone() is not None


def index_exists(cursor, table_name, index_name, schema=None):
    """== ``odoo.tools.sql.index_exists``: ¿existe el índice? (``STATISTICS``)."""
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM information_schema.STATISTICS '
            'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s '
            'LIMIT 1', [table_name, index_name])
    else:
        cursor.execute(
            'SELECT 1 FROM information_schema.STATISTICS '
            'WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s '
            'LIMIT 1', [schema, table_name, index_name])
    return cursor.fetchone() is not None
