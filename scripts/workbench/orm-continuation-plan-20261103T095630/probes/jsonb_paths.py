"""Sonda: tipo Python de cada valor jsonb por ruta de lectura (TASK-API-0504).

Se ejecuta con pytest sobre la base de pruebas; imprime una tabla.
"""
import psycopg
import pytest
from django.db import connection

from orm.environments import Environment, execute_query
from orm.utils import SUPERUSER_ID
from tools.sql import SQL

pytestmark = pytest.mark.django_db

CASES = [
    ('json object', """'{"a": 1}'::json"""),
    ('jsonb object', """'{"a": 1}'::jsonb"""),
    ('jsonb array', """'[1, 2]'::jsonb"""),
    ('jsonb string', """'"x"'::jsonb"""),
    ('jsonb number', """'3'::jsonb"""),
    ('jsonb boolean', """'true'::jsonb"""),
    ('jsonb null', """'null'::jsonb"""),
    ('SQL NULL', """NULL::jsonb"""),
    ('jsonb -> (jsonb)', """('{"a": "b"}'::jsonb) -> 'a'"""),
    ('jsonb ->> (text)', """('{"a": "b"}'::jsonb) ->> 'a'"""),
]


def _show(path, value):
    print(f'| {path} | {type(value).__name__} | {value!r} |')


def test_probe(db):
    select = 'SELECT ' + ', '.join(sql for _, sql in CASES)
    print('\n| ruta / caso | tipo | valor |\n|---|---|---|')
    params = connection.get_connection_params()
    with psycopg.connect(**params) as raw, raw.cursor() as cursor:
        cursor.execute(select)
        for (name, _), value in zip(CASES, cursor.fetchone()):
            _show(f'psycopg directo: {name}', value)
    with connection.cursor() as cursor:
        cursor.execute(select)
        for (name, _), value in zip(CASES, cursor.fetchone()):
            _show(f'cursor de Django: {name}', value)
    for (name, _), value in zip(CASES, execute_query(SQL(select))[0]):
        _show(f'execute_query del ORM: {name}', value)
    with Environment(None, SUPERUSER_ID, {}) as env:
        discussion = env['test_orm.discussion'].create(
            {'name': 'd', 'history': {'n': [1]}})
        model = type(discussion)
        _show('JSONField por QuerySet', model.objects.filter(
            pk=discussion.id).values_list('history', flat=True).get())
        _show('Json leído por el recordset', discussion.history)
        discussion.write({'attributes_definition': [
            {'name': 'tag', 'type': 'char', 'string': 'Tag'}]})
        message = env['test_orm.message'].create(
            {'discussion': discussion.id, 'name': 'm'})
        message.write({'attributes': {'tag': 'alpha'}})
        _show('Properties leído por el recordset', message.attributes)
        _show('get_property_definition', env['test_orm.message']._from_ids(
            env, (), ()).get_property_definition('attributes.tag'))
