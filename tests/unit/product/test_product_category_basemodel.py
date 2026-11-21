"""``product.category`` como ``BaseModel``, completo.

≙ ``odoo19c: addons/product/models/product_category.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-category-basemodel.md``.

*Métrica:* el nombre completo y la ruta del árbol que el ORM mantiene, el
conteo de la rama, el rechazo de un ciclo, ``name_create``, el nombre según
``hierarchical_naming`` y la copia.
*Ciega a:* el hilo de mensajes de ``mail.thread``: se comprueba que el
modelo lo hereda, no los seguidores.
"""
import pytest

from addons.mail.models import MailThread
from addons.product.models import ProductCategory
from exceptions import UserError, ValidationError
from orm.environments import env
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

CATEGORY = 'product.category'


def _category(name, parent=None):
    vals = {'name': name}
    if parent is not None:
        vals['parent_id'] = parent.id
    [category] = env()[CATEGORY].create([vals])
    return category


def test_the_category_is_a_basemodel_with_a_thread():
    assert issubclass(ProductCategory, BaseModel)
    assert issubclass(ProductCategory, MailThread)


def test_the_complete_name_and_the_path_follow_the_tree():
    root = _category('PC Raíz')
    child = _category('PC Hija', root)
    assert child.complete_name == 'PC Raíz / PC Hija'
    assert child.parent_path == f'{root.id}/{child.id}/'


def test_renaming_the_parent_renames_the_children():
    root = _category('PC Antes')
    child = _category('PC Rama', root)
    root.write({'name': 'PC Después'})
    child.invalidate_recordset()
    assert child.complete_name == 'PC Después / PC Rama'


def test_the_product_count_covers_the_branch():
    root = _category('PC Conteo')
    child = _category('PC Conteo hija', root)
    env()['product.template'].create([
        {'name': 'PC P1', 'categ_id': root.id},
        {'name': 'PC P2', 'categ_id': child.id},
    ])
    assert root.product_count == 2
    assert child.product_count == 1


def test_writing_a_cycle_is_refused():
    """La rechaza ya ``_parent_store_update`` («Recursion Detected.»), antes
    de la restricción, como en la fuente."""
    root = _category('PC Ciclo')
    child = _category('PC Ciclo hija', root)
    with pytest.raises(UserError):
        root.write({'parent_id': child.id})


def test_the_recursion_constraint_sees_a_cycle():
    """≙ ``_check_category_recursion``: el ciclo se fuerza por debajo del
    ORM para medir la restricción sola."""
    root = _category('PC Ciclo directo')
    child = _category('PC Ciclo directo hija', root)
    ProductCategory.objects.filter(pk=root.id).update(parent_id=child.id)
    root.invalidate_recordset()
    with pytest.raises(ValidationError):
        root._check_category_recursion()


def test_name_create_returns_the_id_and_the_name():
    category_id, name = env()[CATEGORY].name_create('PC Rápida')
    assert env()[CATEGORY].browse(category_id).name == 'PC Rápida'
    assert name == 'PC Rápida'


def test_the_flat_name_on_request():
    root = _category('PC Plano')
    child = _category('PC Plano hija', root)
    assert child.display_name == 'PC Plano / PC Plano hija'
    flat = child.with_context(hierarchical_naming=False)
    assert flat.display_name == 'PC Plano hija'


def test_the_copy_marks_its_name():
    category = _category('PC Original')
    [vals] = category.copy_data()
    assert vals['name'] == 'PC Original (copy)'
