"""Las clases de dependencia que el marcado de creación tiene que cubrir.

Selección representativa de la matriz
``outputs/stored-compute-fields-20261112.tsv`` para las clases que los
controles de ``test_create_protection.py`` no tocan, con los modelos de
``test_orm`` que la fuente declara para eso (``odoo19c:
odoo/addons/test_orm/models/test_orm.py``):

- dependencia por many2one (``parent_id.name``) y grupo readonly de dos
  campos (``size1``/``size2``, un solo ``_compute_sizes``);
- calculado editable sobre un campo propio (``cost`` ← ``name``);
- agregación hacia arriba por un x2many (``parent.cost`` ← ``child_ids.cost``):
  el alta del hijo tiene que marcar al padre, que es el recorrido inverso de
  ``_modified`` y no un campo del propio registro.

Las dos vías de alta: ``objects.create`` (receptor de ``post_save``) y
``BaseModel.create``.
"""
import pytest
from django.apps import apps

from orm.environments import env as current_env
from orm.environments import transaction_scope

pytestmark = pytest.mark.django_db

Parent = apps.get_model('test_orm', 'TestOrmModelParentM2o')
Child = apps.get_model('test_orm', 'TestOrmModelChildM2o')


def _flush():
    with transaction_scope():
        current_env().flush_all()


def _child(pk):
    return Child.objects.values('size1', 'size2', 'cost').get(pk=pk)


def _parent_cost(pk):
    return Parent.objects.values_list('cost', flat=True).get(pk=pk)


def test_django_creation_covers_many2one_group_and_aggregation():
    parent = Parent.objects.create(name='abc')
    child = Child.objects.create(name='xy', parent_id=parent)
    _flush()
    assert _child(child.pk) == {'size1': 3, 'size2': 3, 'cost': 2}
    assert _parent_cost(parent.pk) == 2


def test_orm_creation_covers_many2one_group_and_aggregation():
    parents = current_env()['test_orm.model_parent_m2o'].sudo()
    parent = parents.create({'name': 'abc'})
    child = current_env()['test_orm.model_child_m2o'].sudo().create(
        {'name': 'xy', 'parent_id': parent.id})
    child.flush_model()
    parent.flush_model()
    assert _child(child.id) == {'size1': 3, 'size2': 3, 'cost': 2}
    assert _parent_cost(parent.id) == 2


def test_an_explicit_editable_cost_survives_the_creation():
    parent = Parent.objects.create(name='abc')
    child = Child.objects.create(name='xy', parent_id=parent, cost=40)
    _flush()
    assert _child(child.pk)['cost'] == 40
    assert _parent_cost(parent.pk) == 40
