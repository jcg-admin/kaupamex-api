"""Los cinco nombres de la fuente en ``product.supplierinfo``.

≙ ``odoo19c: addons/product/models/product_supplierinfo.py:25``
(``product_uom_id``), ``:33`` (``company_id``), ``:36`` (``currency_id``),
``:42`` (``product_id``) y ``:47`` (``product_tmpl_id``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-supplierinfo-source-names.md``.

*Métrica:* el nombre y la columna de cada campo; el filtro de proveedores
por compañía y por variante, que compara ids; y lo que ``save`` deduce.
*Ciega a:* la selección completa de ``_select_seller``, que cubre
``tests/unit/product/test_product_models.py``.
"""
import pytest

from addons.base.models import ResCompany, ResPartner
from addons.product.models import (
    ProductProduct, ProductSupplierinfo, ProductTemplate)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name', [
    'product_uom_id', 'company_id', 'currency_id', 'product_id',
    'product_tmpl_id'])
def test_the_field_keeps_the_source_name_and_column(name):
    assert ProductSupplierinfo._meta.get_field(name).column == name


@pytest.fixture
def template():
    return ProductTemplate.objects.create(name='Insumo psi-src')


@pytest.fixture
def partner():
    return ResPartner.objects.create(name='Proveedor psi-src')


def test_the_filter_keeps_rows_of_the_company_or_of_none(template, partner):
    own = ResCompany.objects.create(code='psi-src-a', name='Propia')
    other = ResCompany.objects.create(code='psi-src-b', name='Ajena')
    variant = ProductProduct.objects.create(product_tmpl=template)
    shared = ProductSupplierinfo.objects.create(
        partner_id=partner, product_tmpl_id=template)
    mine = ProductSupplierinfo.objects.create(
        partner_id=partner, product_tmpl_id=template, company_id=own)
    ProductSupplierinfo.objects.create(
        partner_id=partner, product_tmpl_id=template, company_id=other)
    kept = ProductSupplierinfo._get_filtered_supplier(
        template.seller_ids.all(), own, variant)
    assert set(kept) == {shared, mine}


def test_the_filter_drops_rows_of_another_variant(template, partner):
    variant = ProductProduct.objects.create(product_tmpl=template)
    other = ProductProduct.objects.create(
        product_tmpl=ProductTemplate.objects.create(name='Otro psi-src'))
    general = ProductSupplierinfo.objects.create(
        partner_id=partner, product_tmpl_id=template)
    specific = ProductSupplierinfo.objects.create(
        partner_id=partner, product_tmpl_id=template, product_id=variant)
    ProductSupplierinfo.objects.create(
        partner_id=partner, product_tmpl_id=template, product_id=other)
    kept = ProductSupplierinfo._get_filtered_supplier(
        template.seller_ids.all(), None, variant)
    assert set(kept) == {general, specific}


def test_save_derives_the_template_and_seeds_the_unit(template, partner):
    variant = ProductProduct.objects.create(product_tmpl=template)
    info = ProductSupplierinfo.objects.create(
        partner_id=partner, product_id=variant)
    assert info.product_tmpl_id == template
    assert info.product_uom_id == template.uom
