"""``env.cr.cache``: la caché por cursor.

≙ ``BaseCursor.cache`` (``odoo19c: odoo/sql_db.py:164-174``), vaciada sólo
al cerrar (``odoo19c: odoo/sql_db.py:525-540``). Aquí el cursor del entorno
es la conexión de Django. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/cursor-cache.md``.

*Métrica:* identidad y contenido del diccionario tras cada corte.
*Ciega a:* el reparto entre hilos, que hereda el de las conexiones de Django.
"""
import pytest
from django.db import connection

from orm.environments import env
from sql_db import Cursor

pytestmark = pytest.mark.django_db(transaction=True)


def test_the_cursor_cache_is_one_dict_per_connection():
    cache = env().cr.cache
    assert isinstance(cache, dict)
    assert env().cr.cache is cache


def test_it_survives_commit_and_rollback():
    env().cr.cache['key'] = 'value'
    connection.commit()
    connection.rollback()
    assert env().cr.cache['key'] == 'value'


def test_close_drops_it():
    env().cr.cache['key'] = 'value'
    first = env().cr.cache
    connection.close()
    assert env().cr.cache is not first
    assert 'key' not in env().cr.cache


def test_a_cursor_reads_the_cache_of_its_connection():
    # Bajo prueba no se abre una conexión real (``Registry.cursor()`` da un
    # ``TestCursor``): se mide la delegación sobre la conexión en curso.
    cr = Cursor.__new__(Cursor)
    cr._cnx = connection
    cr.cache['key'] = 1
    assert connection.cache['key'] == 1
    assert cr.cache is env().cr.cache
