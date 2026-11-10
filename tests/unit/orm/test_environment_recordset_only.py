"""Los métodos de recordset sólo se llaman sobre un recordset (G3).

Con ``env[model_name]`` devolviendo el recordset vacío —``odoo19c:
odoo/orm/environments.py:105-107``— ya no hace falta que la clase responda
como si fuera uno. La fuente no tiene equivalente al descriptor que
inyectaba el recordset vacío del entorno activo cuando el método se llamaba
sobre la clase, ni ``BaseModel.__ror__``: ``browse``, ``new``, ``_write``,
``flush_model``, ``invalidate_model`` y el resto son métodos de instancia
(``odoo19c: odoo/orm/models.py``). Diseño en
``designs/environment-getitem-recordset.md``, G3.
"""
import inspect

import pytest

from orm.environments import Environment
from orm.models import BaseModel
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

NAME = 'test_orm.shared.compute'
#: Los nueve métodos que el descriptor envolvía.
RECORDSET_METHODS = (
    'flush_model', 'invalidate_model', '_write', 'browse', 'new',
    'check_access_rights', '_is_an_ordinary_table',
    'check_field_access_rights', '_determine_fields_to_fetch',
)


@pytest.fixture
def env(db):
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


@pytest.mark.parametrize('name', RECORDSET_METHODS)
def test_the_method_is_a_plain_instance_method(name):
    # el descriptor copiaba ``__wrapped__``: ``inspect.unwrap`` no lo
    # distinguiría; el tipo del atributo sí. ``flush_model`` e
    # ``invalidate_model`` se cuelgan en la clase desde fuera de su cuerpo,
    # así que se leen con ``inspect.getattr_static``.
    assert inspect.isfunction(inspect.getattr_static(BaseModel, name))


def test_the_class_does_not_union_on_the_right():
    assert '__ror__' not in vars(BaseModel)


def test_browse_on_the_class_is_not_a_recordset(env):
    # sin ``self`` la tupla ocupa su lugar y el método falla al usarla
    with pytest.raises((TypeError, AttributeError)):
        type(env[NAME]).browse((1,))


def test_browse_on_the_empty_recordset_keeps_its_environment(env):
    records = env[NAME].browse((1, 2))
    assert records._ids == (1, 2)
    assert records.env is env
