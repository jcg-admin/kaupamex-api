"""Atributos de clase de modelo — tarea #330, :ref:`h-api-680`.

Fiel a ``.claude/rules/atributos-de-clase-de-modelo.md``: si la clase de la
referencia declara atributos de clase, se portan TODOS los que declare.
Verifica los tres modelos a los que este pase les completó la cabecera:

- ``odoo19c: addons/stock/models/stock_package.py:18-23`` — ``StockPackage``.
- ``odoo19c: addons/stock/models/stock_package_type.py:8-10`` —
  ``StockPackageType``.
- ``odoo19c: addons/stock/models/product_strategy.py:17-20`` —
  ``StockPutawayRule``.
"""
import pytest

from addons.stock.models import StockPackage, StockPackageType, StockPutawayRule

pytestmark = [pytest.mark.unit]


class TestStockPackageClassAttributes:
    def test_name(self):
        assert StockPackage._name == 'stock.package'

    def test_description(self):
        assert StockPackage._description == 'Package'

    def test_order(self):
        # odoo19c stock_package.py:20 — ``_order = 'name, id'``.
        assert StockPackage._order == 'name, id'

    def test_parent_name_points_to_the_current_containers_tree(self):
        # odoo19c stock_package.py:21 — el árbol ACTUAL, no el de DESTINO.
        assert StockPackage._parent_name == 'parent_package'

    def test_parent_store(self):
        assert StockPackage._parent_store is True

    def test_rec_name(self):
        assert StockPackage._rec_name == 'complete_name'


class TestStockPackageTypeClassAttributes:
    def test_name(self):
        assert StockPackageType._name == 'stock.package.type'

    def test_description(self):
        assert StockPackageType._description == 'Stock package type'

    def test_order(self):
        assert StockPackageType._order == 'sequence, id'


class TestStockPutawayRuleClassAttributes:
    def test_name(self):
        assert StockPutawayRule._name == 'stock.putaway.rule'

    def test_description(self):
        assert StockPutawayRule._description == 'Putaway Rule'

    def test_order(self):
        assert StockPutawayRule._order == 'sequence,product_id'

    def test_check_company_auto(self):
        assert StockPutawayRule._check_company_auto is True
