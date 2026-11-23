"""``purchase_stock`` reescribe la regla de compra al renombrar el almacén.

≙ ``_update_name_and_code`` (``odoo19c: addons/purchase_stock/models/
stock.py:116-122``): el eslabón de ``purchase_stock`` corre sobre el
recordset del almacén y reemplaza la **primera** ocurrencia del nombre
anterior en la regla de compra.
"""

import pytest

from addons.base.models import ResCompany
from addons.stock.models import (
    StockLocation,
    StockRoute,
    StockRule,
    StockWarehouse,
)
from orm.environments import set_current_company


@pytest.fixture
def company(db):
    company_rec = ResCompany.objects.create(code='test_wrn', name='Test WRN')
    set_current_company(company_rec.pk)
    yield company_rec
    set_current_company(None)


def test_renaming_the_warehouse_renames_its_buy_rule(company):
    view = StockLocation.objects.create(
        name='WRN', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='WRN-VIEW')
    stock = StockLocation.objects.create(
        name='WRN/Stock', usage=StockLocation.USAGE_INTERNAL, location=view,
        company=company, barcode='WRN-STOCK')
    route = StockRoute.objects.create(name='Comprar')
    rule = StockRule.objects.create(
        name='Main: Main Comprar', action='buy', route=route,
        location_dest=stock)
    warehouse = StockWarehouse.objects.create(
        name='Main', code='WRN', company=company, view_location=view,
        lot_stock=stock, buy_pull=rule)

    warehouse._update_name_and_code('Central')

    assert StockRule.objects.get(pk=rule.pk).name == 'Central: Main Comprar'
