"""``product.combo`` y ``product.combo.item``: los nombres de la fuente.

≙ ``odoo19c: addons/product/models/product_combo.py:14`` y
``odoo19c: addons/product/models/product_combo_item.py:12-14``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-combo-source-names.md``.

*Métrica:* el nombre y la columna de los cuatro campos y la compañía que la
opción hereda de su elección. La validación de compañía la mide
``test_product_combo_basemodel.py``.
*Ciega a:* ``currency_id`` de las dos clases, que no tienen columna.
"""
import pytest

from addons.base.models.res_company import ResCompany
from addons.product.models import (
    ProductCombo, ProductComboItem, ProductProduct, ProductTemplate)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('model, name', [
    (ProductCombo, 'company_id'),
    (ProductComboItem, 'combo_id'),
    (ProductComboItem, 'product_id'),
    (ProductComboItem, 'company_id'),
])
def test_the_field_keeps_the_source_name_and_column(model, name):
    assert model._meta.get_field(name).column == name


def _variant(name):
    return ProductProduct.objects.create(
        product_tmpl_id=ProductTemplate.objects.create(name=name))


def test_an_option_takes_the_company_of_its_choice():
    company = ResCompany.objects.create(name='Empresa pc')
    combo = ProductCombo.objects.create(name='Bebida pc', company_id=company)
    item = ProductComboItem.objects.create(combo_id=combo,
                                           product_id=_variant('Agua pc'))
    item.refresh_from_db()
    assert item.company_id == company
