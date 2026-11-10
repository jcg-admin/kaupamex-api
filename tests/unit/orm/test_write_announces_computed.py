"""``write`` anuncia los campos calculados que escribe.

≙ ``odoo19c: odoo/orm/models.py:4440-4493`` (``self.modified(vals)`` tras
escribir). Diseño en ``designs/write-announces-computed.md`` del Workbench
(TASK-API-0511, hallazgo H-API-1209).

*Métrica:* el valor en la base tras el volcado y los campos que llegan a
``_modified``.
*Ciega a:* la marca espuria de una lectura previa (H-API-1210): ningún caso
lee ``parent_id`` antes de escribir.
"""
import pytest

import orm.models as orm_models
from orm.environments import Environment
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


@pytest.fixture
def announced(monkeypatch):
    calls = []
    original = orm_models._modified

    def spy(self, fields, create):
        calls.extend((field.model.__name__, field.name) for field in fields)
        return original(self, fields, create)

    monkeypatch.setattr(orm_models, '_modified', spy)
    return calls


def test_writing_a_computed_field_recomputes_its_dependents(env, family):
    parent, child = family
    child.write({'cost': 7})
    parent.flush_model()
    assert type(parent).objects.get(pk=parent.id).cost == 7


def test_an_ordinary_field_is_announced_once(env, family, announced):
    parent, _child = family
    parent.write({'name': 'pqrs'})
    assert announced.count(('TestOrmModelParentM2o', 'name')) == 1


def test_the_written_value_prevails_over_its_own_compute(env, family):
    _parent, child = family
    child.write({'cost': 7})
    child.flush_model()
    assert type(child).objects.get(pk=child.id).cost == 7


def test_an_ordinary_field_still_marks_its_dependents(env, family):
    parent, child = family
    parent.write({'name': 'pqrs'})
    child.flush_model()
    assert type(child).objects.get(pk=child.id).size1 == 4
