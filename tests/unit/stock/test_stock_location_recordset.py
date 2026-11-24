"""``stock.location`` con su identidad y sobre el recordset de la fuente.

≙ ``odoo19c: addons/stock/models/stock_location.py:14-20, 80, 220-295``:
``_name``, el reverso ``quant_ids``, ``write`` que propaga el archivado a la
rama, ``unlink`` de la rama ``child_of`` y ``copy_data`` con «(copy)».
"""
from decimal import Decimal

import pytest

from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import StockLocation, StockQuant
from exceptions import UserError
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree():
    parent = StockLocation.objects.create(name='U6b', usage='view')
    child = StockLocation.objects.create(
        name='Hija', usage='internal', location=parent)
    grandchild = StockLocation.objects.create(
        name='Nieta', usage='internal', location=child)
    return parent, child, grandchild


@pytest.fixture
def variant():
    template = ProductTemplate.objects.create(
        name='Tuerca U6b', list_price=Decimal('1.00'))
    return ProductProduct.objects.create(product_tmpl_id=template)


def test_location_declares_the_reference_identity(tree):
    parent, child, _grandchild = tree
    assert StockLocation._name == 'stock.location'
    assert StockLocation._description == 'Inventory Locations'
    assert StockLocation._parent_store is True
    assert isinstance(parent, BaseModel)
    assert child.location == parent
    assert child in parent.child_ids


def test_quant_ids_is_the_reverse_of_the_quant_location(tree, variant):
    _parent, child, _grandchild = tree
    quant = StockQuant.objects.create(
        product=variant, location=child, quantity=Decimal('2.00'))
    assert quant.id in child.quant_ids.ids
    assert not child.is_empty


def test_archiving_a_branch_archives_its_children(tree):
    parent, child, grandchild = tree
    parent.write({'active': False})
    assert not StockLocation.objects.get(pk=child.pk).active
    assert not StockLocation.objects.get(pk=grandchild.pk).active


def test_archiving_a_branch_with_stock_below_is_refused(tree, variant):
    parent, _child, grandchild = tree
    StockQuant.objects.create(
        product=variant, location=grandchild, quantity=Decimal('1.00'))
    with pytest.raises(UserError):
        parent.write({'active': False})
    assert StockLocation.objects.get(pk=grandchild.pk).active


def test_unlink_deletes_the_whole_branch(tree):
    parent, child, grandchild = tree
    parent.unlink()
    assert not StockLocation.objects.filter(
        pk__in=[parent.pk, child.pk, grandchild.pk]).exists()


def test_copy_names_the_duplicate(tree):
    _parent, child, _grandchild = tree
    duplicate = child.copy()
    assert duplicate.name == 'Hija (copy)'
    assert duplicate.id != child.id
