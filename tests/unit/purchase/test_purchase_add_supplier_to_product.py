"""Al confirmar, el proveedor entra en ``seller_ids`` del producto.

≙ ``odoo19c: addons/purchase/models/purchase_order.py:670-707`` y
``purchase_order_line.py:36,96,266-278,753-758``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-add-supplier-to-product.md``.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResPartner
from addons.product.models import ProductSupplierinfo
from addons.uom.models import Uom
from orm.environments import sudo
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


def _confirm(partner, product, price='40.00', **line_values):
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': partner.pk}])
    MODELS_BY_NAME['purchase.order.line'].create([{
        'order_id': order.id, 'name': 'Insumo', 'product_id': product.pk,
        'price_unit': Decimal(price), **line_values}])
    order.button_confirm()
    return order


def _sellers(product):
    return list(ProductSupplierinfo.objects.filter(
        product_tmpl=product.product_tmpl).order_by('sequence', 'id'))


def test_a_new_vendor_is_added_with_the_source_values():
    vendor = ResPartner.objects.create(name='Proveedor S1', is_company=True)
    product = make_product(name='Insumo S1')
    ProductSupplierinfo.objects.create(
        partner_id=ResPartner.objects.create(name='Otro S1'),
        product_tmpl=product.product_tmpl, sequence=4, price=1)
    _confirm(vendor, product, discount=Decimal('5'))
    added = _sellers(product)[-1]
    assert added.partner_id_id == vendor.pk
    assert added.price == Decimal('40.00')
    assert added.sequence == 5
    assert added.min_qty == 1
    assert added.discount == Decimal('5')
    assert added.delay == 0


def test_a_contact_adds_its_company():
    company = ResPartner.objects.create(name='Empresa S2', is_company=True)
    contact = ResPartner.objects.create(name='Ana S2', parent=company)
    product = make_product(name='Insumo S2')
    _confirm(contact, product)
    assert [s.partner_id_id for s in _sellers(product)] == [company.pk]


def test_an_existing_vendor_is_not_duplicated():
    vendor = ResPartner.objects.create(name='Proveedor S3', is_company=True)
    product = make_product(name='Insumo S3')
    ProductSupplierinfo.objects.create(
        partner_id=vendor, product_tmpl=product.product_tmpl, price=1)
    _confirm(vendor, product)
    assert len(_sellers(product)) == 1


def test_more_than_ten_vendors_adds_nothing():
    product = make_product(name='Insumo S4')
    for index in range(11):
        ProductSupplierinfo.objects.create(
            partner_id=ResPartner.objects.create(name=f'P{index} S4'),
            product_tmpl=product.product_tmpl, price=1)
    vendor = ResPartner.objects.create(name='Proveedor S4', is_company=True)
    _confirm(vendor, product)
    assert len(_sellers(product)) == 11


def test_another_unit_converts_the_price_to_the_template_unit():
    unit = Uom.objects.create(name='Units S5', relative_factor=1.0)
    dozen = Uom.objects.create(name='Dozen S5', relative_factor=12,
                               relative_uom_id=unit)
    product = make_product(name='Insumo S5', uom=unit)
    vendor = ResPartner.objects.create(name='Proveedor S5', is_company=True)
    _confirm(vendor, product, price='120.00', product_uom_id=dozen.pk)
    assert _sellers(product)[-1].price == Decimal('10.00')


def test_a_contact_already_selling_adds_nothing():
    """``already_seller`` mira la empresa Y el contacto (``:689``)."""
    company = ResPartner.objects.create(name='Empresa S6', is_company=True)
    contact = ResPartner.objects.create(name='Luis S6', parent=company)
    product = make_product(name='Insumo S6')
    ProductSupplierinfo.objects.create(
        partner_id=contact, product_tmpl=product.product_tmpl, price=1)
    _confirm(contact, product)
    assert [s.partner_id_id for s in _sellers(product)] == [contact.pk]


def test_the_selected_seller_carries_its_product_name_and_code(monkeypatch):
    """La rama de ``selected_seller_id`` (``:700-703``).

    ``_select_seller`` sólo devuelve tarifas del contacto o de su empresa
    (``odoo19c: product/models/product_product.py:1040``), y esas dos ya son
    ``already_seller``: por el flujo de la fuente la rama la alcanza un addon
    que redefine la selección. El caso la alcanza igual, redefiniendo el
    cómputo.
    """
    other = ResPartner.objects.create(name='Otro S7', is_company=True)
    product = make_product(name='Insumo S7')
    foreign = ProductSupplierinfo.objects.create(
        partner_id=other, product_tmpl=product.product_tmpl, price=1,
        product_name='Nombre del proveedor', product_code='COD-S7')
    line_model = MODELS_BY_NAME['purchase.order.line']

    def _compute_selected_seller_id(self):
        for line in self:
            line.selected_seller_id = foreign

    monkeypatch.setattr(line_model, '_compute_selected_seller_id',
                        _compute_selected_seller_id)
    vendor = ResPartner.objects.create(name='Proveedor S7', is_company=True)
    _confirm(vendor, product)
    added = [s for s in _sellers(product) if s.partner_id_id == vendor.pk]
    assert [(s.product_name, s.product_code) for s in added] == [
        ('Nombre del proveedor', 'COD-S7')]
