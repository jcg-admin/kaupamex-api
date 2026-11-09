"""``_inherits`` con dos padres: cada nombre va al padre que lo publica.

Contrato de ``odoo19c``: ``_inherits`` admite varios padres
(``odoo/orm/models.py:407-425``) y, con un nombre repetido, *"the inherited
field will correspond to the last one (in the inherits list order)"*;
``_add_inherited_fields`` (``odoo/orm/model_classes.py:480-508``) lo
resuelve con un dict por comprensión en ese orden, y ``create`` crea o
escribe cada padre (``models.py:4692-4707``).

Ningún modelo de ``odoo19c`` declara dos padres (recorrido AST, 0), así que
el modelo ``test_orm.related_inherits_two`` es propio: padre A
``test_orm.related`` (``name``, ``foo_id``), padre B ``test_orm.related_bar``
(``name``, ``active``). Diseño en
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/``.

*Métrica:* valores leídos por el hijo y persistidos en cada padre.
*Ciega a:* tres o más padres y ``_inherits`` a través de varios niveles.
"""
import pytest

from orm.environments import env as current_env
from orm.environments import sudo
from orm.inherits import ensure_inherits
from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry

pytestmark = pytest.mark.django_db

CHILD = 'test_orm.related_inherits_two'


@pytest.fixture
def parents():
    with sudo():
        e = current_env()
        foo = e['test_orm.related_foo'].create({'name': 'foo'})
        a = e['test_orm.related'].create({'name': 'a-name', 'foo_id': foo.id})
        b = e['test_orm.related_bar'].create({'name': 'b-name',
                                              'active': False})
        yield e, foo, a, b


def test_the_registry_publishes_the_last_parent_for_a_shared_name():
    fields = model_field_registry(MODELS_BY_NAME[CHILD])
    assert fields['name'].inherited
    assert fields['name'].related.split('.')[0].startswith('bar_parent_id')
    assert fields['foo_id'].related.split('.')[0].startswith('base_id')
    assert fields['active'].related.split('.')[0].startswith('bar_parent_id')


def test_reads_go_to_the_parent_that_owns_the_name(parents):
    e, foo, a, b = parents
    with sudo():
        child = e[CHILD].create({'base_id': a.id, 'bar_parent_id': b.id})
        row = MODELS_BY_NAME[CHILD]._base_manager.get(pk=child.id)
        assert row.name == 'b-name'
        assert row.active is False
        assert row.foo_id.pk == foo.id


def test_writes_go_to_the_parent_that_owns_the_name(parents):
    e, foo, a, b = parents
    with sudo():
        child = e[CHILD].create({'base_id': a.id, 'bar_parent_id': b.id})
        child.write({'name': 'renamed', 'active': True})
        e.flush_all()
        A = MODELS_BY_NAME['test_orm.related']._base_manager.get(pk=a.id)
        B = MODELS_BY_NAME['test_orm.related_bar']._base_manager.get(pk=b.id)
        assert (A.name, B.name, B.active) == ('a-name', 'renamed', True)


def test_create_without_parents_creates_both(parents):
    e, foo, a, b = parents
    with sudo():
        child = e[CHILD].create({'name': 'born', 'foo_id': foo.id,
                                 'active': True})
        e.flush_all()
        row = MODELS_BY_NAME[CHILD]._base_manager.get(pk=child.id)
        A = row.base_id
        B = row.bar_parent_id
        assert (A.foo_id.pk, B.name, B.active) == (foo.id, 'born', True)
        assert A.name is None


def test_create_with_one_parent_given_creates_the_other(parents):
    e, foo, a, b = parents
    with sudo():
        child = e[CHILD].create({'base_id': a.id, 'name': 'born'})
        e.flush_all()
        row = MODELS_BY_NAME[CHILD]._base_manager.get(pk=child.id)
        assert row.base_id.pk == a.id
        assert row.bar_parent_id.name == 'born'
        A = MODELS_BY_NAME['test_orm.related']._base_manager.get(pk=a.id)
        assert A.name == 'a-name'


def test_installing_twice_keeps_one_wrapper_per_hook(parents):
    e, foo, a, b = parents
    model = MODELS_BY_NAME[CHILD]
    hooks = (model.__getattr__, model.__setattr__, model.save)
    ensure_inherits()
    assert (model.__getattr__, model.__setattr__, model.save) == hooks
    with sudo():
        child = e[CHILD].create({'base_id': a.id, 'bar_parent_id': b.id})
        row = model._base_manager.get(pk=child.id)
        assert (row.name, row.foo_id.pk) == ('b-name', foo.id)
