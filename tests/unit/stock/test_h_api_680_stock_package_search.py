"""Guion bajo restaurado en ``StockPackage`` — tarea #330, :ref:`h-api-680`.

Los siete métodos de búsqueda de ``odoo19c: addons/stock/models/
stock_package.py:208-276`` habían perdido su guion bajo en el puerto
(``porte-completo-no-parcial.md``, H-API-581). Este archivo prueba, por su
nombre correcto y su comportamiento, tres de los siete (los que se arman con
menos fixtures); los otros cuatro (``_search_location_dest_id``,
``_search_move_line_ids``, ``_search_outermost_package_id``,
``_search_picking_ids``) sólo se prueban por existencia — su comportamiento
ya lo cubre la suite de integración de ``stock`` vía ``move_line_ids`` /
``picking_ids``, que los invoca indirectamente.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResPartner
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import StockLocation, StockPackage, StockQuant

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def location(db):
    return StockLocation.objects.create(name='WH/Stock', usage='internal')


@pytest.fixture
def variant(db):
    template = ProductTemplate.objects.create(
        name='Camisa', list_price=Decimal('100.00'))
    return ProductProduct.objects.create(product_tmpl=template)


@pytest.fixture
def partner(db):
    return ResPartner.objects.create(name='Cliente H680')


SEARCH_METHOD_NAMES = (
    '_search_all_children_package_ids',
    '_search_contained_quant_ids',
    '_search_location_dest_id',
    '_search_move_line_ids',
    '_search_outermost_package_id',
    '_search_owner',
    '_search_picking_ids',
)

OLD_PUBLIC_NAMES = (
    'search_all_children_package_ids', 'search_contained_quant_ids',
    'search_location_dest', 'search_move_line_ids',
    'search_outermost_package', 'search_owner', 'search_picking_ids',
)


class TestUnderscoreContract:
    """Los siete nombres restaurados existen; los siete públicos viejos, no."""

    @pytest.mark.parametrize('method_name', SEARCH_METHOD_NAMES)
    def test_exists_with_leading_underscore(self, method_name):
        assert hasattr(StockPackage, method_name)

    @pytest.mark.parametrize('old_name', OLD_PUBLIC_NAMES)
    def test_old_public_name_no_longer_exists(self, old_name):
        assert not hasattr(StockPackage, old_name)


class TestSearchOwner:
    def test_finds_packages_of_the_owner(self, location, variant, partner):
        # odoo19c stock_package.py:261-264
        package = StockPackage.objects.create(name='PACK-1')
        StockQuant.objects.create(
            product=variant, location=location, package=package,
            owner=partner, quantity=Decimal('5.00'))
        result = StockPackage._search_owner([partner])
        assert package in result

    def test_without_quants_of_the_owner_it_does_not_appear(
            self, location, variant, partner):
        StockPackage.objects.create(name='PACK-2')
        result = StockPackage._search_owner([partner])
        assert list(result) == []


class TestSearchAllChildrenPackageIds:
    def test_returns_the_ancestors_via_parent_path(self):
        # odoo19c stock_package.py:208-210 — ``parent_of`` sobre parent_path.
        grandparent = StockPackage.objects.create(name='ABUELO')
        parent = StockPackage.objects.create(
            name='PADRE', parent_package=grandparent)
        child = StockPackage.objects.create(
            name='HIJO', parent_package=parent)
        result = StockPackage._search_all_children_package_ids([child])
        assert set(result) == {grandparent, parent, child}

    def test_without_parent_path_returns_empty(self):
        assert list(StockPackage._search_all_children_package_ids([])) == []


class TestSearchContainedQuantIds:
    def test_finds_the_package_that_contains_the_quant(
            self, location, variant):
        # odoo19c stock_package.py:212-217
        package = StockPackage.objects.create(name='PACK-3')
        quant = StockQuant.objects.create(
            product=variant, location=location, package=package,
            quantity=Decimal('2.00'))
        result = StockPackage._search_contained_quant_ids([quant])
        assert package in result

    def test_without_direct_packages_returns_empty(self, location, variant):
        quant = StockQuant.objects.create(
            product=variant, location=location, quantity=Decimal('1.00'))
        result = StockPackage._search_contained_quant_ids([quant])
        assert list(result) == []
