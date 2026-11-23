"""``stock.putaway.rule`` sin categoría de almacenamiento prueba el destino.

≙ ``_get_putaway_location`` (``odoo19c: addons/stock/models/
product_strategy.py:150-155``): ``if not putaway_rule.storage_category_id``
decide por la verdad del Many2one. Desde que la regla y la categoría son
``BaseModel``, una regla sin categoría la lee como recordset vacío, no como
``None``; la prueba fija que entonces se devuelve el destino directo y no una
sububicación que ya tenga existencias.
"""

import pytest

from addons.base.models import ResCompany
from addons.stock.models import StockLocation
from addons.stock.models.product_strategy import StockPutawayRule
from orm.environments import set_current_company
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


@pytest.fixture
def company(db):
    """Empresa activa para las ubicaciones y la regla."""
    company = ResCompany.objects.create(code='test_putaway', name='Putaway')
    set_current_company(company.pk)
    yield company
    set_current_company(None)


def test_rule_without_category_returns_its_destination(company):
    view = StockLocation.objects.create(
        name='PW', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='PW-VIEW')
    stock = StockLocation.objects.create(
        name='PW/Stock', usage=StockLocation.USAGE_INTERNAL, location=view,
        company=company, barcode='PW-STOCK')
    shelf = StockLocation.objects.create(
        name='PW/Stock/Shelf', usage=StockLocation.USAGE_INTERNAL,
        location=stock, company=company, barcode='PW-SHELF')
    rule = StockPutawayRule.objects.create(
        location_in=stock, location_out=stock, company=company)

    assert not rule.storage_category
    found = rule.get_putaway_location(
        make_product(), quantity=1, qty_by_location={shelf.pk: 1})

    assert found == stock
