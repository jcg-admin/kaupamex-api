"""Agrupado y formato por propiedades en ``_read_group`` y ``read_group``.

≙ ``odoo19c: odoo/orm/models.py:2935-3041`` y ``:2638-2744``. Diseño en
``designs/read-group-properties.md`` del Workbench.

*Métrica:* los grupos devueltos sobre mensajes con propiedades sembradas.
*Ciega a:* propiedades ``many2many`` y ``datetime`` (sin caso aquí) y el
comodelo transitorio o abstracto, que la validación de la definición no deja
escribir.
"""
import warnings

import pytest
from django.db import connection

from exceptions import UserError
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def seeded(env):
    red, blue = env['test_orm.category'].create(
        [{'name': 'red'}, {'name': 'blue'}])
    discussion = env['test_orm.discussion'].create({'name': 'd'})
    discussion.write({'attributes_definition': [
        {'name': 'tag', 'type': 'char', 'string': 'Tag'},
        {'name': 'state', 'type': 'selection', 'string': 'State',
         'selection': [['open', 'Open'], ['done', 'Done']]},
        {'name': 'cat', 'type': 'many2one', 'string': 'Cat',
         'comodel': 'test_orm.category'},
        {'name': 'labels', 'type': 'tags', 'string': 'Labels',
         'tags': [['a', 'A', 1], ['b', 'B', 2]]},
        {'name': 'note_html', 'type': 'html', 'string': 'Note'},
    ]})
    first, second, third = env['test_orm.message'].create([
        {'discussion': discussion.id, 'name': 'first'},
        {'discussion': discussion.id, 'name': 'second'},
        {'discussion': discussion.id, 'name': 'third'},
    ])
    first.write({'attributes': {'tag': 'alpha', 'state': 'open',
                                'cat': red.id, 'labels': ['a', 'b']}})
    second.write({'attributes': {'tag': 'beta', 'state': 'done',
                                 'cat': red.id, 'labels': ['a']}})
    # El tercero apunta a una categoría que deja de existir y lleva una
    # etiqueta que la definición no declara: la escritura del ORM no deja
    # escribirla, así que se pone en la columna, como quedaría en la base.
    third.write({'attributes': {'cat': blue.id}})
    blue.unlink()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE test_orm_message SET attributes = attributes || "
            "'{\"labels\": [\"zzz\"]}'::jsonb WHERE id = %s", [third.id])
    return red, blue, first | second | third


def _groups(env, messages, spec):
    rows = env['test_orm.message']._read_group(
        [('id', 'in', messages.ids)], [spec], ['__count'])
    pairs = [((value.id if hasattr(value, '_ids') else value), count)
             for value, count in rows]
    return sorted(pairs, key=str)


def _by_text(pairs):
    return sorted(pairs, key=str)


def test_a_char_property_groups_by_value_and_false(env, seeded):
    _red, _blue, messages = seeded
    assert _by_text(_groups(env, messages, 'attributes.tag')) == _by_text(
        [('alpha', 1), ('beta', 1), (False, 1)])


def test_a_selection_property_groups_by_valid_option(env, seeded):
    _red, _blue, messages = seeded
    assert _groups(env, messages, 'attributes.state') == sorted(
        [('done', 1), ('open', 1), (False, 1)], key=str)


def test_a_many2one_property_groups_by_existing_record(env, seeded):
    red, _blue, messages = seeded
    rows = _groups(env, messages, 'attributes.cat')
    assert sorted(rows, key=str) == sorted(
        [(red.id, 2), (False, 1)], key=str)


def test_a_many2one_property_is_formatted_with_its_name(env, seeded):
    red, _blue, messages = seeded
    model = env['test_orm.message']._from_ids(env, (), ())
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        rows = model.read_group([('id', 'in', messages.ids)], ['__count'],
                                ['attributes.cat'])
    named = [row['attributes.cat'] for row in rows if row['attributes.cat']]
    assert named == [(red.id, 'red')]


def test_a_tags_property_gives_one_group_per_valid_tag(env, seeded):
    _red, _blue, messages = seeded
    assert sorted(_groups(env, messages, 'attributes.labels'),
                  key=str) == sorted(
        [('a', 2), ('b', 1), (False, 1)], key=str)


def test_an_html_property_cannot_be_grouped(env, seeded):
    _red, _blue, messages = seeded
    with pytest.raises(UserError, match='HTML'):
        env['test_orm.message']._read_group(
            [('id', 'in', messages.ids)], ['attributes.note_html'],
            ['__count'])
