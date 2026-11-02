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

import pytest

from addons.test_orm.models.test_orm import TestOrmDiscussion
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
