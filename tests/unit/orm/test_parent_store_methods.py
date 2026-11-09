"""``BaseModel._parent_store_update_prepare`` y ``_parent_store_update``.

≙ ``odoo19c: odoo/orm/models.py:4985-5054``. Diseño en
``designs/parent-store-update-methods.md`` del Workbench.

*Métrica:* los registros devueltos y los ``parent_path`` resultantes.
*Ciega a:* el orden de volcado del caché frente a otras escrituras.
"""
import pytest

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
def tree(env):
    Category = env['test_orm.category']
    root_a = Category.create({'name': 'a'})
    root_b = Category.create({'name': 'b'})
    child = Category.create({'name': 'c', 'parent': root_a.id})
    leaf = Category.create({'name': 'l', 'parent': child.id})
    return root_a, root_b, child, leaf


def test_prepare_returns_only_the_records_whose_parent_changes(env, tree):
    root_a, root_b, child, leaf = tree
    records = child | leaf
    moved = records._parent_store_update_prepare(
        [{'parent': root_b.id}, {'name': 'same'}])
    assert moved.ids == [child.id]


def test_prepare_ignores_a_parent_that_does_not_change(env, tree):
    root_a, _root_b, child, _leaf = tree
    assert not child._parent_store_update_prepare([{'parent': root_a.id}])


def test_update_rewrites_the_records_and_their_descendants(env, tree):
    root_a, root_b, child, leaf = tree
    type(child).objects.filter(pk=child.id).update(parent=root_b.id)
    child._parent_store_update()
    paths = dict(type(child).objects.filter(
        pk__in=[child.id, leaf.id]).values_list('id', 'parent_path'))
    assert paths[child.id] == f'{root_b.id}/{child.id}/'
    assert paths[leaf.id] == f'{root_b.id}/{child.id}/{leaf.id}/'


def test_moving_under_a_descendant_is_rejected(env, tree):
    _root_a, _root_b, child, leaf = tree
    type(child).objects.filter(pk=child.id).update(parent=leaf.id)
    with pytest.raises(UserError, match='Recursion'):
        child._parent_store_update()


def test_write_goes_through_the_methods(env, tree, monkeypatch):
    root_a, root_b, child, leaf = tree
    calls = []
    model = type(child)
    original = model._parent_store_update

    def spy(self):
        calls.append(tuple(self.ids))
        return original(self)

    monkeypatch.setattr(model, '_parent_store_update', spy)
    child.write({'parent': root_b.id})
    assert calls == [(child.id,)]
    paths = dict(model.objects.filter(
        pk__in=[child.id, leaf.id]).values_list('id', 'parent_path'))
    assert paths[leaf.id] == f'{root_b.id}/{child.id}/{leaf.id}/'


def test_write_without_a_parent_change_does_not_rewrite(env, tree,
                                                        monkeypatch):
    root_a, _root_b, child, _leaf = tree
    calls = []
    model = type(child)
    monkeypatch.setattr(model, '_parent_store_update',
                        lambda self: calls.append(self.ids))
    child.write({'parent': root_a.id, 'name': 'renamed'})
    assert calls == []
