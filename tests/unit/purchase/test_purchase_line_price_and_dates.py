"""Precio, fecha prevista y descripción de la línea de compra.

≙ ``odoo19c: addons/purchase/models/purchase_order_line.py:25-28,146-152,
334-351,366-395,404-475,535-551,602-611,701-715``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-line-price-and-dates.md``.
"""
import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import connection

from addons.account.models import AccountFiscalPosition, AccountTax
from addons.base.models import ResCompany, ResPartner
from addons.product.models import ProductSupplierinfo
from addons.uom.models import Uom
from orm.environments import company_scope, sudo
from orm.migration_operations import ComputeStoredFields
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db
LINE = 'purchase.order.line'


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    """La fuente corre con ``env.company`` siempre fijada."""
    company = ResCompany.objects.create(name='Compras precio 0122')
    with company_scope(company.pk):
        yield company


@pytest.fixture(autouse=True)
def unit():
    """La fuente exige ``uom_id`` en todo producto (``required=True``)."""
    return Uom.objects.create(name='Units P5', relative_factor=1.0)


@pytest.fixture
def vendor():
    return ResPartner.objects.create(name='Proveedor precio 0122')


def _order(company, vendor, **values):
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id, **values}])
    return order


def _product(unit, **values):
    return make_product(uom=unit, **values)


def _line(order, product, **values):
    [line] = MODELS_BY_NAME[LINE].create([{
        'order_id': order.id, 'product_id': product.pk,
        'product_qty': Decimal('1'), **values}])
    return line


def _seller(vendor, product, **values):
    values.setdefault('price', Decimal('7'))
    return ProductSupplierinfo.objects.create(
        partner_id=vendor, product_tmpl=product.product_tmpl, **values)


def test_the_seller_price_and_discount_fill_a_new_line(company, vendor, unit):
    product = _product(unit, name='Insumo P5')
    _seller(vendor, product, price=Decimal('7'), discount=Decimal('10'))
    line = _line(_order(company, vendor), product)
    assert line.price_unit == Decimal('7')
    assert line.technical_price_unit == Decimal('7')
    assert line.discount == Decimal('10')


def test_a_manual_price_is_not_overwritten(company, vendor, unit):
    product = _product(unit, name='Insumo manual P5')
    _seller(vendor, product, price=Decimal('7'))
    line = _line(_order(company, vendor), product,
                 price_unit=Decimal('99'))
    assert line.price_unit == Decimal('99')


def test_without_seller_the_standard_price_is_used(company, vendor, unit):
    product = _product(unit, name='Insumo costo P5',
                       standard_price=Decimal('12'))
    line = _line(_order(company, vendor), product)
    assert line.price_unit == Decimal('12')
    assert line.discount == Decimal('0')


def test_the_seller_delay_sets_the_expected_arrival(company, vendor, unit):
    product = _product(unit, name='Insumo plazo P5')
    _seller(vendor, product, delay=5)
    date_order = datetime.datetime(2026, 3, 2, 10, 0,
                                   tzinfo=datetime.timezone.utc)
    line = _line(_order(company, vendor, date_order=date_order), product)
    assert line.date_planned == date_order + datetime.timedelta(days=5)


def test_get_date_planned_without_order_date_counts_from_today():
    model = MODELS_BY_NAME[LINE]
    seller = ProductSupplierinfo(delay=3)
    planned = model()._get_date_planned(seller)
    expected = datetime.datetime.today() + datetime.timedelta(days=3)
    assert abs(planned - expected) < datetime.timedelta(seconds=5)


def test_the_name_is_the_purchase_description(company, vendor, unit):
    product = _product(unit, name='Insumo nombre P5',
                       description_purchase='Lote certificado')
    line = _line(_order(company, vendor), product)
    assert line.name == f'{product.display_name}\nLote certificado'


def test_a_custom_name_is_kept(company, vendor, unit):
    product = _product(unit, name='Insumo propio P5')
    line = _line(_order(company, vendor), product, name='Mi descripción')
    assert line.name == 'Mi descripción'


def test_suggest_quantity_takes_the_vendor_minimum(company, vendor, unit):
    product = _product(unit, name='Insumo mínimo P5')
    _seller(vendor, product, min_qty=3)
    line = _line(_order(company, vendor), product, price_unit=Decimal('1'))
    line._suggest_quantity()
    assert line.product_qty == 3


def test_suggest_quantity_defaults_to_one(company, vendor, unit):
    product = _product(unit, name='Insumo uno P5')
    line = _line(_order(company, vendor), product, price_unit=Decimal('1'),
                 product_qty=Decimal('5'))
    line._suggest_quantity()
    assert line.product_qty == 1


def test_compute_tax_id_maps_supplier_taxes_through_the_position(
        company, vendor, unit):
    tax = AccountTax.objects.create(
        name='IVA compra P5', amount=16, type_tax_use='purchase',
        company=company)
    product = _product(unit, name='Insumo impuesto P5')
    product.product_tmpl.supplier_taxes.set([tax])
    order = _order(company, vendor)
    line = _line(order, product, price_unit=Decimal('1'))
    line._compute_tax_id()
    assert list(line.tax_ids.all()) == [tax]
    replacement = AccountTax.objects.create(
        name='Exento P5', amount=0, type_tax_use='purchase', company=company)
    replacement.original_tax_ids.set([tax])
    position = AccountFiscalPosition.objects.create(
        name='Exención P5', company=company)
    position.tax_ids.set([replacement])
    order.fiscal_position_id = position
    order.save()
    line._compute_tax_id()
    assert list(line.tax_ids.all()) == [replacement]


def test_onchange_product_id_resets_and_suggests(company, vendor, unit):
    product = _product(unit, name='Insumo cambio P5')
    _seller(vendor, product, price=Decimal('4'), min_qty=2)
    line = _line(_order(company, vendor), product, price_unit=Decimal('50'),
                 product_qty=Decimal('9'))
    line.onchange_product_id()
    assert line.product_qty == 2
    # El precio se reinicia a 0 y la nueva cantidad vuelve a calcularlo
    # desde la tarifa (``_compute_price_unit_and_date_planned_and_name``
    # depende de ``product_qty``), que es lo que el comentario de la fuente
    # anuncia: *"_onchange_quantity will provide default values"*.
    assert line.price_unit == Decimal('4')
    assert line.product_uom_id == product.uom
    assert line.name == product.display_name


def test_convert_to_middle_of_day_uses_the_buyer_timezone(
        company, vendor, unit):
    order = _order(company, vendor)
    order.company_id.partner.tz = 'America/Mexico_City'
    order.company_id.partner.save()
    order.user_id = None
    line = _line(order, _product(unit, name='Insumo tz P5'),
                 price_unit=Decimal('1'))
    noon = line._convert_to_middle_of_day(datetime.date(2026, 1, 15))
    assert noon == datetime.datetime(2026, 1, 15, 18, 0)


def test_update_date_planned_assigns_the_date(company, vendor, unit):
    line = _line(_order(company, vendor), _product(unit, name='Insumo u P5'),
                 price_unit=Decimal('1'))
    when = datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc)
    line._update_date_planned(when)
    assert line.date_planned == when


def test_migration_computes_the_date_of_existing_rows(company, vendor, unit):
    """Escenario C: una fila anterior a la columna recibe su valor."""
    product = _product(unit, name='Insumo migración P5')
    _seller(vendor, product, delay=2)
    line = _line(_order(company, vendor), product)
    MODELS_BY_NAME[LINE].objects.filter(pk=line.pk).update(date_planned=None)
    migration = importlib.import_module(
        'addons.purchase.migrations.0022_line_date_planned')
    [operation] = [op for op in migration.Migration.operations
                   if isinstance(op, ComputeStoredFields)]
    operation.code(apps, connection.schema_editor())
    line.refresh_from_db()
    assert line.date_planned is not None
