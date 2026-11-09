"""``jsonb`` decodificado en las consultas crudas del ORM (TASK-API-0504).

La fuente corre sobre psycopg2, que decodifica ``jsonb`` en el cursor; aquí
Django registra ``TextLoader`` para ``jsonb`` en la conexión
(``django/db/backends/postgresql/psycopg_any.py``). Diseño en
``designs/orm-raw-query-jsonb.md`` del Workbench.

*Métrica:* los tipos que devuelven ``execute_query`` y ``execute_query_dict``.
*Ciega a:* los consumidores que el cambio alcanza; los mide la regresión.
"""
import pytest
from django.db import connection

from orm.environments import Environment, execute_query
from orm.utils import SUPERUSER_ID
from tools.sql import SQL

pytestmark = pytest.mark.django_db

VALUES = SQL("""SELECT '{"a": 1}'::jsonb, '[1, 2]'::jsonb, '"x"'::jsonb,
                       '3'::jsonb, 'null'::jsonb, NULL::jsonb""")
DECODED = ({'a': 1}, [1, 2], 'x', 3, None, None)


def test_execute_query_decodes_jsonb():
    assert execute_query(VALUES) == [DECODED]


def test_execute_query_dict_decodes_jsonb():
    with Environment(None, SUPERUSER_ID, {}) as env:
        rows = env.execute_query_dict(SQL(
            """SELECT '{"a": 1}'::jsonb AS obj, '"x"'::jsonb AS text"""))
    assert rows == [{'obj': {'a': 1}, 'text': 'x'}]


def test_json_is_unchanged():
    assert execute_query(SQL("""SELECT '{"a": 1}'::json""")) == [({'a': 1},)]


def test_a_django_cursor_still_reads_jsonb_as_text():
    execute_query(VALUES)
    with connection.cursor() as cursor:
        cursor.execute("""SELECT '{"a": 1}'::jsonb""")
        assert cursor.fetchone() == ('{"a": 1}',)


def test_a_json_field_is_not_decoded_twice():
    with Environment(None, SUPERUSER_ID, {}) as env:
        discussion = env['test_orm.discussion'].create(
            {'name': 'd', 'history': {'delete_messages': [7]}})
        model = type(discussion)
        assert model.objects.filter(pk=discussion.id).values_list(
            'history', flat=True).get() == {'delete_messages': [7]}
