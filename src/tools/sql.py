"""Introspección SQL sobre ``information_schema`` (fiel a ``odoo.tools.sql``).

``odoo/tools/sql.py`` ofrece ``table_exists``/``column_exists``/``index_exists``
sobre ``information_schema``. Tras migrar el motor a PostgreSQL estas tres
convergen con la referencia y ya **no** hay traducción que mantener: el "current
schema" vuelve a ser ``current_schema`` (``odoo19c: odoo/tools/sql.py:320``),
que bajo MariaDB había que escribir como ``DATABASE()``.

El cambio no es cosmético — ``schema`` significa otra cosa en cada motor:

  ============  =====================================  ========================
  Motor         ``schema=None`` resuelve a             ``schema='x'`` designa
  ============  =====================================  ========================
  MariaDB       ``DATABASE()`` — la base conectada     una **base**
  PostgreSQL    ``current_schema`` — normalmente       un **namespace** dentro
                ``public``                             de la base (no otra base)
  ============  =====================================  ========================

Un consumidor que pasaba el nombre de la base como ``schema`` funcionaba en
MariaDB y aquí no encontraría nada. Medido a HEAD: **0** consumidores en
``src/`` pasan ``schema`` explícito, así que el cambio de significado no rompe
código vivo — pero queda escrito porque el próximo que lo use tiene que saberlo.
Ver H-API-306.

``index_exists`` cambia de catálogo: PostgreSQL no tiene
``information_schema.STATISTICS`` (es una tabla de MySQL). La referencia usa
``pg_indexes`` (``odoo19c: odoo/tools/sql.py:542``), y aquí se conserva además
el filtro por tabla que nuestra firma ya exponía.

Además expone ``SQL`` (fiel a la clase componible ``odoo.tools.SQL``), que un
addon portado importa como ``from tools.sql import SQL``. Respaldo Django:
``SQL`` = ``django.db.models.expressions.RawSQL`` (fragmento SQL parametrizado
embebible en un ``QuerySet``, equivalente al rol de ``odoo.tools.SQL``).
"""
from django.db.models.expressions import RawSQL

SQL = RawSQL                       # Odoo tools.SQL ≈ Django RawSQL


def table_exists(cursor, table_name, schema=None):
    """== ``odoo.tools.sql.table_exists``: ¿existe la tabla?

    ``schema=None`` → el schema de la conexión (``current_schema``).
    """
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM information_schema.tables '
            'WHERE table_schema = current_schema AND table_name = %s',
            [table_name])
    else:
        cursor.execute(
            'SELECT 1 FROM information_schema.tables '
            'WHERE table_schema = %s AND table_name = %s',
            [schema, table_name])
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name, schema=None):
    """== ``odoo.tools.sql.column_exists``: ¿existe la columna?"""
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM information_schema.columns '
            'WHERE table_schema = current_schema AND table_name = %s AND column_name = %s',
            [table_name, column_name])
    else:
        cursor.execute(
            'SELECT 1 FROM information_schema.columns '
            'WHERE table_schema = %s AND table_name = %s AND column_name = %s',
            [schema, table_name, column_name])
    return cursor.fetchone() is not None


def table_columns(cursor, table_name, schema=None):
    """== ``odoo.tools.sql.table_columns``: columnas de la tabla y su forma.

    Devuelve ``{nombre: {udt_name, character_maximum_length, is_nullable}}``.
    Fiel a ``odoo19c: odoo/tools/sql.py`` — incluida su omisión deliberada de
    ``character_octet_length``, que su comentario justifica: en hospedaje
    compartido (Heroku, OVH) el rol de la aplicación puede no tener permiso
    para leer esa columna, y pedirla haría fallar la consulta entera.

    La referencia devuelve el ``row`` de ``dictfetchall()``; aquí se arma el
    diccionario a mano porque el cursor de Django devuelve tuplas.
    """
    if schema is None:
        cursor.execute(
            'SELECT column_name, udt_name, character_maximum_length, is_nullable '
            'FROM information_schema.columns '
            'WHERE table_name = %s AND table_schema = current_schema',
            [table_name])
    else:
        cursor.execute(
            'SELECT column_name, udt_name, character_maximum_length, is_nullable '
            'FROM information_schema.columns '
            'WHERE table_name = %s AND table_schema = %s',
            [table_name, schema])
    return {
        fila[0]: {
            'column_name': fila[0],
            'udt_name': fila[1],
            'character_maximum_length': fila[2],
            'is_nullable': fila[3],
        }
        for fila in cursor.fetchall()
    }


def index_exists(cursor, table_name, index_name, schema=None):
    """== ``odoo.tools.sql.index_exists``: ¿existe el índice? (``pg_indexes``)."""
    if schema is None:
        cursor.execute(
            'SELECT 1 FROM pg_indexes '
            'WHERE schemaname = current_schema AND tablename = %s AND indexname = %s '
            'LIMIT 1', [table_name, index_name])
    else:
        cursor.execute(
            'SELECT 1 FROM pg_indexes '
            'WHERE schemaname = %s AND tablename = %s AND indexname = %s '
            'LIMIT 1', [schema, table_name, index_name])
    return cursor.fetchone() is not None
