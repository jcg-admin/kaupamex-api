"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_json_field.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1`` (Community 19). La prueba de
la fuente ejerce el contrato de ``Json`` (``odoo19c: odoo/orm/fields_misc.py:
55-87``): el registro recibe una COPIA del valor en caché
(``convert_to_record`` → ``copy.deepcopy``), la caché guarda la forma JSON
normalizada (``convert_to_cache`` → ida y vuelta por ``json``) y la escritura
persiste en ``jsonb``.

**Adaptación declarada:** ``flush_recordset`` de la fuente se traduce a
``save()`` + relectura desde la base, que es el punto en que este stack
materializa la escritura. ``env.cache.get`` se traduce a la caché del ORM
(``field._get_cache(env)``) y al almacén Django de la fila, los dos planos que
el descriptor consulta (``src/orm/fields.py``, ``FieldDescriptor.__get__``).

El fixture crea la discusión sólo con ``name``, como la fuente: su
``moderator`` es opcional desde que H-API-1122 se resolvió para ``test_orm``.
"""

import datetime

import pytest

import fields

from addons.test_orm.models.test_orm import TestOrmDiscussion
from orm.domains import Domain
from orm.environments import env as get_environment

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

RANDOM_STR = 'tVpajMuSvaR94DwSRVtRSLGNkKViNbWHt2hq13'
RANDOM_STR_2 = 'Crypto-money base'


@pytest.fixture
def discussion():
    return TestOrmDiscussion.objects.create(name='Test Discussion JSON field')


def _cached_values(record):
    """Los objetos que el descriptor puede devolver para ``history``."""
    field = type(record)._meta.get_field('history')
    values = [record.__dict__.get(field.attname)]
    cache = field._get_cache(get_environment())
    if record.pk in cache:
        values.append(cache[record.pk])
    return values


def _reloaded(record):
    return TestOrmDiscussion.objects.get(pk=record.pk)


def test_default_is_the_declared_literal(discussion):
    assert discussion.history == {'delete_messages': []}
    assert _reloaded(discussion).history == {'delete_messages': []}


def test_read_returns_a_copy_not_the_cached_value(discussion):
    """≙ ``:21`` — ``assertIsNot(history, env.cache.get(...))``."""
    value = discussion.history
    for cached in _cached_values(discussion):
        assert value is not cached
    assert discussion.history is not discussion.history


def test_mutating_the_read_value_does_not_change_the_record(discussion):
    """El documento de la fuente: Json no implementa «mutating the values»."""
    discussion.history['delete_messages'].append(RANDOM_STR)
    assert discussion.history == {'delete_messages': []}


def test_write_read_cycle_persists(discussion):
    """≙ ``:25-36`` — escritura, volcado y lectura, incluida la tupla."""
    discussion.history = {'delete_messages': [RANDOM_STR]}
    discussion.save()
    assert discussion.history == {'delete_messages': [RANDOM_STR]}
    assert _reloaded(discussion).history == {'delete_messages': [RANDOM_STR]}

    discussion.history = {'delete_messages': [RANDOM_STR, RANDOM_STR_2]}
    discussion.save()
    assert _reloaded(discussion).history == {
        'delete_messages': [RANDOM_STR, RANDOM_STR_2]}

    # ``:33-36`` — una tupla sale como lista: la caché es la forma JSON.
    discussion.history = (RANDOM_STR, RANDOM_STR_2)
    assert discussion.history == [RANDOM_STR, RANDOM_STR_2]
    discussion.save()
    assert _reloaded(discussion).history == [RANDOM_STR, RANDOM_STR_2]


# ``Json.convert_to_cache`` (``odoo19c: odoo/orm/fields_misc.py:70-73``):
# todo valor falso se guarda como ``None``, y ``convert_to_record`` lo
# entrega como ``False``. La columna ``jsonb`` de la fuente admite ``NULL``.


def test_a_json_field_is_nullable_by_default():
    assert fields.Json().null is True
    assert fields.Json(null=False).null is False


def test_an_empty_value_is_stored_as_null(discussion):
    discussion.write({'history': {}})
    assert _reloaded(discussion).__dict__['history'] is None
    assert discussion.history is False


def test_the_cache_of_a_falsy_value_is_none():
    field = TestOrmDiscussion._meta.get_field('history')
    assert field.null is True
    for falsy in ({}, [], '', 0, False, None):
        assert field.convert_to_cache(falsy, None) is None


def test_the_cache_serializes_with_json_default():
    """``convert_to_cache`` serializa con ``json_default``
    (``odoo19c: odoo/orm/fields_misc.py:73``): un instante sale como
    ``Datetime.to_string``, una fecha como ``Date.to_string`` y un ``Domain``
    como su lista."""
    field = TestOrmDiscussion._meta.get_field('history')
    value = field.convert_to_cache({
        'at': datetime.datetime(2026, 11, 3, 4, 5, 6),
        'on': datetime.date(2026, 11, 3),
        'domain': Domain('name', '=', 'x'),
    }, None)
    assert value == {'at': '2026-11-03 04:05:06', 'on': '2026-11-03',
                     'domain': [['name', '=', 'x']]}
