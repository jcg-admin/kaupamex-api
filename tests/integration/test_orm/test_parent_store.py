"""``_parent_store`` — ≙ ``_parent_store_create`` y ``_parent_store_update``
(``odoo19c: odoo/orm/models.py:4961-5054``).

La fuente mantiene ``parent_path`` (``'1/4/9/'``) con dos ``UPDATE``: uno al
crear, que concatena la ruta del padre y el id propio, y otro al cambiar de
padre, que reescribe el prefijo de la fila y de todos sus descendientes.
``test_orm.category`` declara ``_parent_store = True`` con ``parent``.
"""

import pytest

from exceptions import UserError

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def tree(env):
    Category = env['test_orm.category']
    root = Category.create({'name': 'root'})
    child = Category.create({'name': 'child', 'parent': root.id})
    leaf = Category.create({'name': 'leaf', 'parent': child.id})
    other = Category.create({'name': 'other'})
    return root, child, leaf, other


def _path(env, record):
    return type(env['test_orm.category']).objects.get(
        pk=record.id).parent_path


def test_create_sets_the_materialized_path(env, tree):
    root, child, leaf, _ = tree
    assert _path(env, root) == f'{root.id}/'
    assert _path(env, child) == f'{root.id}/{child.id}/'
    assert _path(env, leaf) == f'{root.id}/{child.id}/{leaf.id}/'


def test_reparenting_rewrites_the_descendants(env, tree):
    _, child, leaf, other = tree
    child.write({'parent': other.id})
    assert _path(env, child) == f'{other.id}/{child.id}/'
    assert _path(env, leaf) == f'{other.id}/{child.id}/{leaf.id}/'


def test_a_recursion_is_refused(env, tree):
    root, _, leaf, _ = tree
    with pytest.raises(UserError):
        root.write({'parent': leaf.id})
