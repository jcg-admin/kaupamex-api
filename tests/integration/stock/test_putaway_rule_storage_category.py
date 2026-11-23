"""``stock.putaway.rule`` sobre ``BaseModel``: categoría, cálculo y empresa.

Con categoría de almacenamiento vacía, la regla prueba el destino directo.

≙ ``_get_putaway_location`` (``odoo19c: addons/stock/models/
product_strategy.py:150-155``): ``if not putaway_rule.storage_category_id``
decide por la verdad del Many2one. Desde que la regla y la categoría son
``BaseModel``, una regla sin categoría la lee como recordset vacío, no como
``None``; la prueba fija que entonces se devuelve el destino directo y no una
sububicación que ya tenga existencias. Las demás fijan el cálculo
almacenado de la categoría (``odoo19c: :76-80``) y el rechazo a cambiar de
empresa (``:107-112``).
"""

import pytest

from addons.base.models import ResCompany
from addons.stock.models import StockLocation
from addons.stock.models.product_strategy import StockPutawayRule
from addons.stock.models.stock_storage_category import StockStorageCategory
from exceptions import UserError
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


@pytest.fixture
def stock(company):
    """Una ubicación interna de la empresa activa."""
    return StockLocation.objects.create(
        name='PW2/Stock', usage=StockLocation.USAGE_INTERNAL,
        company=company, barcode='PW2-STOCK')


def test_writing_the_sublocation_clears_the_category(company, stock):
    """≙ ``_compute_storage_category`` (``odoo19c: :76-80``), almacenado.

    El valor dado en ``create`` está protegido y no se recalcula; el
    cambio posterior de ``sublocation`` sí dispara el cálculo.
    """
    category = StockStorageCategory.objects.create(
        name='Seco', company=company)
    rule = StockPutawayRule.create({
        'location_in': stock, 'location_out': stock, 'company': company,
        'storage_category': category, 'sublocation': 'closest_location'})
    assert rule.storage_category == category

    rule.write({'sublocation': 'last_used'})

    rule = StockPutawayRule.objects.get(pk=rule.id)
    assert not rule.storage_category


def test_changing_the_company_is_refused(company, stock):
    """≙ ``write`` (``odoo19c: :107-112``)."""
    rule = StockPutawayRule.create({
        'location_in': stock, 'location_out': stock, 'company': company})
    other = ResCompany.objects.create(code='test_putaway_2', name='Otra')

    with pytest.raises(UserError):
        rule.write({'company': other})
    rule.write({'company': company, 'sequence': 7})
    assert StockPutawayRule.objects.get(pk=rule.id).sequence == 7
