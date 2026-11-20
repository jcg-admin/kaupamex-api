"""Los related y los cómputos sin columna de la línea de compra.

≙ ``odoo19c: addons/purchase/models/purchase_order_line.py:19-21,35,38,42-45,
54,85-90,105-111,152-162,229-235,510-529``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-order-line-port.md`` (unidad 2).
"""
from decimal import Decimal

import pytest
from django.db import models as dj_models

from addons.base.models import ResCompany, ResPartner
from addons.product.models import ProductSupplierinfo
from addons.uom.models import Uom
from orm.environments import env, sudo
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db
LINE = 'purchase.order.line'


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


@pytest.fixture
def order():
    company = ResCompany.objects.create(name='Compras related 0122')
    vendor = ResPartner.objects.create(name='Proveedor related 0122')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    return order


def _line(order, **values):
    defaults = {'order_id': order.id, 'name': 'Insumo', 'product_qty': 1,
                'price_unit': Decimal('100')}
    if 'display_type' not in values and 'product_id' not in values:
        defaults['product_id'] = make_product(name='Insumo related').pk
    [line] = MODELS_BY_NAME[LINE].create([{**defaults, **values}])
    return line


def test_the_order_fields_reach_the_line(order):
    line = _line(order)
    order.button_confirm()
    line.invalidate_recordset()
    assert line.state == 'purchase'
    assert line.date_order == order.date_order
    assert line.date_approve == order.date_approve
    assert line.currency_id == order.currency_id


def test_the_product_and_company_fields_reach_the_line(order):
    product = make_product(name='Servicio related')
    line = _line(order, product_id=product.pk)
    assert line.product_type == product.type
    assert line.tax_calculation_rounding_method == (
        order.company_id.tax_calculation_rounding_method)
    assert list(line.product_template_attribute_value_ids) == list(
        product.product_template_attribute_values.all())


def test_the_related_fields_have_no_column():
    model = MODELS_BY_NAME[LINE]
    for name in ('state', 'date_order', 'date_approve', 'currency_id',
                 'product_type', 'tax_calculation_rounding_method',
                 'product_template_attribute_value_ids',
                 'translated_product_name', 'price_unit_product_uom',
                 'price_unit_discounted', 'parent_id', 'allowed_uom_ids'):
        assert model._fields[name].store is False, name


def test_the_stored_fields_of_the_unit():
    model = MODELS_BY_NAME[LINE]
    field = model._meta.get_field('product_no_variant_attribute_value_ids')
    assert field.remote_field.through._meta.db_table == (
        'product_template_attribute_value_purchase_order_line_rel')
    assert model._meta.get_field('technical_price_unit').concrete
    assert isinstance(model._meta.get_field('name'), dj_models.TextField)


def test_the_translated_product_name_is_its_display_name(order):
    product = make_product(name='Nombre traducido')
    line = _line(order, product_id=product.pk)
    assert line.translated_product_name == product.display_name


def test_the_discounted_unit_price(order):
    line = _line(order, discount=Decimal('10'))
    assert line.price_unit_discounted == Decimal('90')


def test_without_discount_the_discounted_price_is_the_price(order):
    line = _line(order, discount=Decimal('0'))
    assert line.price_unit_discounted == Decimal('100')


def test_the_discounted_price_keeps_decimal_precision(order):
    """``price_unit * (1 - discount / 100)`` sin redondeo, como la fuente
    (``odoo19c: purchase_order_line.py:152-155``), y en ``Decimal``: ningún
    tramo pasa por ``float``."""
    line = _line(order, price_unit=Decimal('99.99'), discount=Decimal('12.5'))
    assert line.price_unit_discounted == Decimal('87.49125')
    assert isinstance(line.price_unit_discounted, Decimal)


def test_a_full_discount_leaves_nothing(order):
    line = _line(order, discount=Decimal('100'))
    assert line.price_unit_discounted == Decimal('0')


def test_a_new_line_without_price_reads_zero():
    line = env()['purchase.order.line'].new({})
    assert line.price_unit_discounted == 0


def test_the_unit_price_in_the_product_unit(order):
    unit = Uom.objects.create(name='Units R2', relative_factor=1.0)
    dozen = Uom.objects.create(name='Dozen R2', relative_factor=12,
                               relative_uom_id=unit)
    product = make_product(name='Insumo R2', uom_id=unit)
    line = _line(order, product_id=product.pk, product_uom_id=dozen.pk,
                 price_unit=Decimal('120'))
    assert line.price_unit_product_uom == pytest.approx(10.0)


def test_a_section_has_no_unit_price_in_the_product_unit(order):
    line = _line(order, display_type='line_section', product_qty=0,
                 price_unit=Decimal('0'))
    assert not line.price_unit_product_uom


def test_the_parent_is_the_last_section_or_subsection(order):
    section = _line(order, display_type='line_section', sequence=1,
                    product_qty=0, price_unit=Decimal('0'))
    first = _line(order, sequence=2)
    sub = _line(order, display_type='line_subsection', sequence=3,
                product_qty=0, price_unit=Decimal('0'))
    second = _line(order, sequence=4)
    assert not section.parent_id
    assert first.parent_id == section
    assert sub.parent_id == section
    assert second.parent_id == sub


def test_the_allowed_units_add_the_vendor_unit(order):
    unit = Uom.objects.create(name='Units R3', relative_factor=1.0)
    box = Uom.objects.create(name='Box R3', relative_factor=6,
                             relative_uom_id=unit)
    product = make_product(name='Insumo R3', uom_id=unit)
    ProductSupplierinfo.objects.create(
        partner_id=order.partner_id, product_tmpl_id=product.product_tmpl_id,
        price=1, product_uom_id=box)
    line = _line(order, product_id=product.pk)
    assert set(line.allowed_uom_ids) == {unit, box}
