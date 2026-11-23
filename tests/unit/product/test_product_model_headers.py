"""Las cabeceras de ``product.supplierinfo`` y ``product.pricelist.item``.

≙ ``odoo19c: addons/product/models/product_supplierinfo.py:8-11`` y
``product_pricelist_item.py:9-12``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-model-headers.md``.

*Métrica:* los atributos de clase, el nombre y la columna de los dos campos
que la cabecera nombra, y las filas de acceso de ``purchase``.
*Ciega a:* ``_check_company_auto`` de la regla de tarifa y los demás
Many2one en forma A, que el diseño declara con su sucesor.
"""
import pytest

from addons.base.models import IrModelData, ResPartner
from addons.product.models import (
    ProductPricelistItem, ProductSupplierinfo, ProductTemplate)

pytestmark = pytest.mark.django_db


def test_the_supplierinfo_header_is_the_reference():
    attrs = ProductSupplierinfo.__dict__
    assert attrs['_name'] == 'product.supplierinfo'
    assert attrs['_description'] == 'Supplier Pricelist'
    assert attrs['_order'] == 'sequence, min_qty DESC, price, id'
    assert attrs['_rec_name'] == 'partner_id'


def test_the_pricelist_item_header_is_the_reference():
    attrs = ProductPricelistItem.__dict__
    assert attrs['_name'] == 'product.pricelist.item'
    assert attrs['_description'] == 'Pricelist Rule'
    assert attrs['_order'] == (
        'applied_on, min_quantity desc, categ_id desc, id desc')


@pytest.mark.parametrize('model, name', [
    (ProductSupplierinfo, 'partner_id'),
    (ProductPricelistItem, 'categ_id'),
])
def test_the_named_field_keeps_the_source_name_and_column(model, name):
    field = model._meta.get_field(name)
    assert field.column == name


def test_the_purchase_access_rows_load():
    names = set(IrModelData.objects.filter(
        module='purchase', model='ir.model.access',
    ).values_list('name', flat=True))
    assert {'access_product_supplierinfo_purchase_manager',
            'access_product_pricelist_item_purchase_manager'} <= names


def test_a_vendor_price_shows_its_vendor():
    """``_rec_name = 'partner_id'``: la tarifa se muestra por su
    proveedor."""
    vendor = ResPartner.objects.create(name='Proveedor Cabecera')
    template = ProductTemplate.objects.create(name='Insumo Cabecera')
    price = ProductSupplierinfo.objects.create(
        partner_id=vendor, product_tmpl_id=template, price=1)
    assert str(price) == str(vendor)
