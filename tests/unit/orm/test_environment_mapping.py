"""``Environment`` como ``Mapping`` — ``get``, ``keys``, ``items``, ``values``.

≙ ``odoo19c: odoo/orm/environments.py:40`` y ``:101-122``. Diseño en
``designs/environment-mapping.md`` del Workbench.

*Métrica:* el protocolo de mapeo del entorno activo.
*Ciega a:* el contenido del registro de modelos, que mide su propia suite.
"""
from collections.abc import Mapping

import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def test_the_environment_is_a_mapping(env):
    assert isinstance(env, Mapping)


def test_get_returns_the_model_or_the_default(env):
    assert env.get('test_orm.category') is env['test_orm.category']
    assert env.get('no.such.model') is None
    assert env.get('no.such.model', 'fallback') == 'fallback'


def test_keys_are_the_model_names(env):
    assert list(env.keys()) == list(env)
    assert 'test_orm.category' in env.keys()


def test_equality_stays_identity(env):
    same = Environment(None, SUPERUSER_ID, {})
    assert (same == env) is (same is env)
    assert hash(env) == object.__hash__(env)
