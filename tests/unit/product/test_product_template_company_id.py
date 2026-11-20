"""``product.template.company_id``: el nombre de la fuente de la compañía.

≙ ``odoo19c: addons/product/models/product_template.py:124``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-template-company-id.md``.

*Métrica:* el nombre y la columna del campo, la delegación en la variante,
la moneda de coste y el lote nuevo de una línea de movimiento, que leen la
compañía del producto por nombre.
*Ciega a:* ``ProductTemplate.uom`` y ``ProductProduct.product_tmpl``, que el
diseño declara con su sucesor.
"""
import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.stock.models import StockMoveLine

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='ptco-a', name='Compania ptco')


@pytest.fixture
def variant(company):
    template = ProductTemplate.objects.create(name='Plantilla ptco',
                                              company_id=company)
    return ProductProduct.objects.create(product_tmpl=template)


def test_company_id_keeps_the_source_name_and_column():
    assert ProductTemplate._meta.get_field(
        'company_id').column == 'company_id'


def test_the_variant_delegates_company_id_to_its_template(variant, company):
    assert variant.company_id == company


def test_the_cost_currency_is_the_one_of_the_product_company(
        variant, company):
    assert variant.product_tmpl.cost_currency == company.currency


def test_a_new_lot_takes_the_company_of_the_product(variant, company):
    line = StockMoveLine(product=variant, company=company, lot_name='L-ptco')
    assert line._prepare_new_lot_vals()['company_id'] == company.pk
