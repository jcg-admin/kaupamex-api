"""Cabecera de ``product.category`` y el nombre de la fuente de su padre.

≙ ``odoo19c: addons/product/models/product_category.py:9-15`` (cabecera)
y ``:21`` (``parent_id``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-category-header.md``.

*Métrica:* los atributos de clase, el nombre y la columna del padre, y el
árbol mantenido a través de ``parent_id``.
*Ciega a:* el hilo de mensajes de ``mail.thread``, ``name_create`` y
``copy_data``, que el diseño declara con su sucesor.
"""
import pytest

from addons.product.models import ProductCategory
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

HEADER = {
    '_name': 'product.category',
    '_inherit': ['mail.thread'],
    '_description': 'Product Category',
    '_parent_name': 'parent_id',
    '_parent_store': True,
    '_rec_name': 'complete_name',
    '_order': 'complete_name',
}


def test_the_header_is_the_reference():
    for name, value in HEADER.items():
        assert ProductCategory.__dict__[name] == value


def test_the_registry_resolves_the_source_name():
    assert MODELS_BY_NAME['product.category'] is ProductCategory


def test_parent_id_keeps_the_source_name_and_column():
    field = ProductCategory._meta.get_field('parent_id')
    assert field.column == 'parent_id'
    assert field.remote_field.model is ProductCategory


def test_the_tree_is_kept_through_parent_id():
    root = ProductCategory.objects.create(name='Raiz cat-hdr')
    child = ProductCategory.objects.create(name='Hija cat-hdr',
                                           parent_id=root)
    assert child.complete_name == 'Raiz cat-hdr / Hija cat-hdr'
    assert child.parent_path == f'{root.pk}/{child.pk}/'
    assert list(root.child_id) == [child]
