"""Leer un ``Many2one`` diferido no anuncia una escritura.

≙ ``odoo19c: odoo/orm/fields.py`` (``Field.__get__`` → ``fetch``): una
lectura puebla la caché y no llama ``modified``. Diseño en
``designs/many2one-deferred-read.md`` del Workbench (TASK-API-0512,
hallazgo H-API-1210).

*Métrica:* el contenido de ``tocompute`` antes y después de la lectura.
*Ciega a:* otros caminos de lectura que no sean la carga diferida.
"""
import pytest

from orm.environments import Environment, get_transaction
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def family(env):
    parent = env['test_orm.model_parent_m2o'].create({'name': 'p'})
    child = env['test_orm.model_child_m2o'].create(
        {'name': 'c', 'parent_id': parent.id, 'cost': 2})
    parent.flush_model()
    child.flush_model()
    return parent, child


def _pending():
    return {(field.model.__name__, field.name): list(ids)
            for field, ids in get_transaction().tocompute.items() if ids}


def test_reading_a_deferred_many2one_marks_nothing(env, family):
    _parent, child = family
    assert _pending() == {}
    child.parent_id
    assert _pending() == {}


def test_the_deferred_read_returns_the_stored_parent(env, family):
    parent, child = family
    assert child.parent_id.id == parent.id


def test_assigning_the_many2one_still_marks_its_dependents(env, family):
    _parent, child = family
    other = type(_parent).create({'name': 'longer'})
    child.parent_id = other
    assert child.id in _pending().get(('TestOrmModelChildM2o', 'size1'), [])
