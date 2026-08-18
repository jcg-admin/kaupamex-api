"""Guion bajo restaurado en ``StockPutawayRule`` — tarea #330, :ref:`h-api-680`.

Los cinco métodos privados de ``odoo19c: addons/stock/models/
product_strategy.py`` habían perdido su guion bajo en el puerto
(``porte-completo-no-parcial.md``, H-API-581). Este archivo prueba, por su
nombre correcto y su comportamiento, los cinco restaurados:

- ``_default_category_id`` (``:22-24``)
- ``_default_location_id`` (``:26-32``)
- ``_default_product_id`` (``:34-40``)
- ``_onchange_sublocation`` (``:82-94``)
- ``_onchange_location_in`` (``:96-100``)
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductCategory, ProductProduct, ProductTemplate
from addons.stock.models import (
    StockLocation,
    StockPutawayRule,
    StockStorageCategory,
    StockWarehouse,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex', code='kaupamex_h680')


@pytest.fixture
def category(db):
    return ProductCategory.objects.create(name='Ropa')


@pytest.fixture
def variant(db):
    template = ProductTemplate.objects.create(
        name='Camisa', list_price=Decimal('100.00'))
    return ProductProduct.objects.create(product_tmpl=template)


class TestUnderscoreContract:
    """Los cinco nombres restaurados existen; los viejos públicos, no."""

    def test_default_category_id_is_private(self):
        assert hasattr(StockPutawayRule, '_default_category_id')
        assert not hasattr(StockPutawayRule, 'default_category')

    def test_default_location_id_is_private(self):
        assert hasattr(StockPutawayRule, '_default_location_id')
        assert not hasattr(StockPutawayRule, 'default_location_in')

    def test_default_product_id_is_private(self):
        assert hasattr(StockPutawayRule, '_default_product_id')
        assert not hasattr(StockPutawayRule, 'default_product')

    def test_onchange_sublocation_is_private(self):
        assert hasattr(StockPutawayRule, '_onchange_sublocation')
        assert not hasattr(StockPutawayRule, 'check_sublocation_category')

    def test_onchange_location_in_is_private(self):
        assert hasattr(StockPutawayRule, '_onchange_location_in')
        assert not hasattr(StockPutawayRule, 'apply_location_in')


class TestDefaultCategoryId:
    def test_from_an_active_category_returns_its_id(self, category):
        # odoo19c product_strategy.py:22-24
        result = StockPutawayRule._default_category_id(
            active_model='product.category', active_id=category.pk)
        assert result == category.pk

    def test_without_active_model_has_no_default(self):
        assert StockPutawayRule._default_category_id() is None

    def test_with_another_active_model_has_no_default(self):
        assert StockPutawayRule._default_category_id(
            active_model='product.product', active_id=1) is None


class TestDefaultLocationId:
    def test_from_an_active_location_returns_its_id(self):
        # odoo19c product_strategy.py:26-28
        assert StockPutawayRule._default_location_id(
            active_model='stock.location', active_id=42) == 42

    def test_with_multi_warehouse_has_no_default(self):
        # odoo19c :29-30 — sin el permiso hace falta resolver un único almacén;
        # con él, ambigüedad, así que no hay default.
        assert StockPutawayRule._default_location_id(multi_warehouse=True) is None

    def test_without_multi_warehouse_uses_the_single_warehouse_input(
            self, company):
        # odoo19c :30-32
        view_loc = StockLocation.objects.create(
            name='WH1', usage=StockLocation.USAGE_VIEW, company=company,
            barcode='H680-VIEW')
        stock_loc = StockLocation.objects.create(
            name='WH1/Stock', usage=StockLocation.USAGE_INTERNAL,
            location=view_loc, company=company, barcode='H680-STOCK')
        warehouse = StockWarehouse.objects.create(
            name='Almacén único', code='WH1', company=company,
            view_location=view_loc, lot_stock=stock_loc)
        result = StockPutawayRule._default_location_id(
            company=company, multi_warehouse=False)
        input_loc, _output_loc = warehouse._get_input_output_locations(
            warehouse.reception_steps, warehouse.delivery_steps)
        assert result == input_loc


class TestDefaultProductId:
    def test_from_an_active_variant_returns_its_id(self):
        # odoo19c product_strategy.py:38-40
        assert StockPutawayRule._default_product_id(
            active_model='product.product', active_id=7) == 7

    def test_from_a_template_with_a_single_variant(self, variant):
        # odoo19c :35-37
        result = StockPutawayRule._default_product_id(
            active_model='product.template', active_id=variant.product_tmpl_id)
        assert result == variant

    def test_without_active_model_has_no_default(self):
        assert StockPutawayRule._default_product_id() is None


class TestOnchangeLocationIn:
    def test_without_a_destination_it_mirrors_the_source(self):
        # odoo19c product_strategy.py:97-98
        source = StockLocation.objects.create(name='Entrada', usage='internal')
        rule = StockPutawayRule(location_in=source)
        result = rule._onchange_location_in()
        assert result == source
        assert rule.location_out == source

    def test_destination_already_child_of_source_is_kept(self):
        # odoo19c :98-99 — si ya cuelga del origen, no se toca.
        source = StockLocation.objects.create(name='Padre', usage='view')
        destination = StockLocation.objects.create(
            name='Hijo', usage='internal', location=source)
        rule = StockPutawayRule(location_in=source, location_out=destination)
        rule._onchange_location_in()
        assert rule.location_out == destination


class TestOnchangeSublocation:
    def test_outside_closest_location_no_warning(self):
        # odoo19c product_strategy.py:84-85 — sólo aplica con sublocation
        # == 'closest_location'.
        rule = StockPutawayRule(sublocation='no')
        assert rule._onchange_sublocation() is None

    def test_with_children_of_the_category_no_warning(self, company):
        destination = StockLocation.objects.create(name='Zona', usage='internal')
        storage_cat = StockStorageCategory.objects.create(
            name='Frío', company=company)
        StockLocation.objects.create(
            name='Zona/Fría', usage='internal', location=destination,
            storage_category=storage_cat)
        rule = StockPutawayRule(
            location_out=destination, storage_category=storage_cat,
            sublocation='closest_location')
        assert rule._onchange_sublocation() is None

    def test_without_children_of_the_category_warns(self, company):
        # odoo19c :86-93 — sin ninguna sububicación con esa categoría, avisa.
        destination = StockLocation.objects.create(
            name='Zona2', usage='internal')
        storage_cat = StockStorageCategory.objects.create(
            name='Seco', company=company)
        rule = StockPutawayRule(
            location_out=destination, storage_category=storage_cat,
            sublocation='closest_location')
        warning_msg = rule._onchange_sublocation()
        assert warning_msg is not None
