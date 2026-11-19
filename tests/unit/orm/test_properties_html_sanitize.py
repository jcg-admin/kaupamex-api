"""El saneo de las propiedades ``*_html``.

≙ ``test_properties_field_html`` (``odoo19c:
odoo/addons/test_orm/tests/test_properties.py:829-897``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
properties-html-sanitize.md``.
"""
import json

import pytest
from django.db import connection

from exceptions import UserError
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

XSS_PAYLOAD = "<img src='x' onerror='alert(1)'/>"
EXPECTED = '<img src="x">'


@pytest.fixture
def env(db, system_user):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def message(env):
    discussion = env['test_orm.discussion'].create(
        {'name': 'd', 'participants': [(6, 0, [env.user.id])]})
    return env['test_orm.message'].create(
        {'discussion': discussion.id, 'name': 'm'})


def _sql_properties(message):
    message.flush_recordset()
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT attributes FROM test_orm_message WHERE id = %s',
            [message.id])
        value = cursor.fetchone()[0] or {}
    # la consulta cruda devuelve el jsonb como texto
    return json.loads(value) if isinstance(value, str) else value


def _write_definition(message):
    message.attributes = [{
        'name': 'test_html',
        'type': 'html',
        'string': 'HTML',
        'default': XSS_PAYLOAD,
        'value': XSS_PAYLOAD,
        'definition_changed': True,
    }]


def test_the_value_is_sanitized_in_the_column_and_the_cache(message):
    _write_definition(message)
    assert _sql_properties(message).get('test_html') == EXPECTED
    assert dict(message.attributes)['test_html'] == EXPECTED
    assert message.attributes['test_html'] == EXPECTED


def test_grouping_by_an_html_property_is_refused(env, message):
    _write_definition(message)
    with pytest.raises(UserError):
        env['test_orm.message']._read_group([], ['attributes.test_html'])


def test_read_returns_the_sanitized_value_and_default(message):
    _write_definition(message)
    properties = message.read(['attributes'])[0]['attributes']
    assert properties[0]['value'] == EXPECTED
    assert properties[0]['default'] == EXPECTED


def test_the_definition_default_is_sanitized(message):
    _write_definition(message)
    definition = message.discussion.attributes_definition
    assert definition[0]['default'] == EXPECTED
    definition = message.discussion.read(
        ['attributes_definition'])[0]['attributes_definition']
    assert definition[0]['default'] == EXPECTED


def test_writing_a_dict_sanitizes(message):
    _write_definition(message)
    message.attributes = {'test_html': XSS_PAYLOAD}
    assert message.attributes['test_html'] == EXPECTED
    properties = message.read(['attributes'])[0]['attributes']
    assert properties[0]['value'] == EXPECTED


def test_the_html_suffix_belongs_to_html_properties(message):
    with pytest.raises(ValueError):
        message.attributes = [{
            'name': 'text_html', 'type': 'text', 'string': 'HTML',
            'default': XSS_PAYLOAD, 'value': XSS_PAYLOAD,
            'definition_changed': True,
        }]
    with pytest.raises(ValueError):
        message.discussion.attributes_definition = [{
            'name': 'text_html', 'type': 'text', 'string': 'HTML',
            'default': XSS_PAYLOAD, 'definition_changed': True,
        }]


def test_a_context_default_is_sanitized(env, message):
    _write_definition(message)
    created = env['test_orm.message'].with_context(
        default_attributes_test_html=XSS_PAYLOAD).create(
            {'discussion': message.discussion.id})
    assert created.attributes['test_html'] == EXPECTED
    assert _sql_properties(created).get('test_html') == EXPECTED
