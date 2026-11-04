"""La preparación de la base-line: de un registro a un diccionario.

≙ ``_get_base_line_field_value_from_record``,
``_import_base_line_extra_tax_data`` y
``_prepare_base_line_for_taxes_computation`` (``odoo19c:
addons/account/models/account_tax.py:1430-1691``, LGPL-3).

La fuente lee ``record[field]`` con sus nombres (``product_id``,
``tax_ids``) y recibe registros. Aquí ``line['product_id']`` es el
``attname`` de la FK —un entero— y ``line['tax_ids']`` un gestor; la
adaptación traduce el nombre con ``_create_field_lookup`` y devuelve el
registro y el ``QuerySet``. Los casos lo miden sobre una ``sale.order.line``
real, y sobre un diccionario, que es la otra forma que admite la fuente.
"""

from decimal import Decimal

import pytest

from addons.account.models import AccountTax
from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency
from addons.sale.models import SaleOrder, SaleOrderLine
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db

load = AccountTax._get_base_line_field_value_from_record


@pytest.fixture
def environment(db):
    with Environment(None, SUPERUSER_ID, {}) as env:
        yield env


@pytest.fixture
def currency(db):
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    return currency


@pytest.fixture
def tax(db):
    company = ResCompany.objects.create(code='linea-base', name='Linea base')
    return AccountTax.objects.create(name='IVA 16', amount=Decimal('16'),
                                     company=company)


@pytest.fixture
def line(environment, tax):
    product = make_product(name='Eleke linea base')
    order = SaleOrder.objects.create()
    sale_line = SaleOrderLine.objects.create(
        order=order, product=product, product_uom_qty=Decimal('2'),
        price_unit=Decimal('10.00'))
    sale_line.tax_ids.set([tax])
    return sale_line


class TestFieldValueFromRecord:
    """≙ ``_get_base_line_field_value_from_record`` (``:1560-1590``)."""

    def test_a_many2one_name_gives_the_record_not_its_id(self, line):
        assert load(line, 'product_id', {}, None) == line.product

    def test_a_many2many_name_gives_a_queryset_of_records(self, line, tax):
        value = load(line, 'tax_ids', {}, AccountTax.objects.none())
        assert list(value) == [tax]
        assert hasattr(value, '_flatten_taxes_and_sort_them')

    def test_extra_values_win_and_fall_back_when_falsy(self, line):
        assert load(line, 'price_unit', {'price_unit': 7}, 0.0) == 7
        assert load(line, 'price_unit', {'price_unit': 0}, 3.0) == 3.0

    def test_from_base_line_skips_the_record(self, line):
        assert load(line, 'price_unit', {}, 5.0, from_base_line=True) == 5.0

    def test_a_dict_and_a_falsy_record(self):
        assert load({'quantity': 4}, 'quantity', {}, 0.0) == 4
        assert load({}, 'quantity', {}, 1.0) == 1.0
        assert load(None, 'quantity', {}, 2.0) == 2.0

    def test_an_absent_field_gives_the_fallback(self, line):
        assert load(line, 'sign', {}, 1.0) == 1.0


class TestImportExtraTaxData:
    """≙ ``_import_base_line_extra_tax_data`` (``:1430-1482``)."""

    def _base_line(self, currency, tax):
        return {
            'tax_ids': AccountTax.objects.filter(pk=tax.pk),
            'currency_id': currency, 'price_unit': 100.0, 'discount': 0.0,
            'quantity': 2.0, 'rate': 2.0,
        }

    def test_the_computation_key_always_passes(self, currency, tax):
        results = AccountTax._import_base_line_extra_tax_data(
            self._base_line(currency, tax),
            {'computation_key': 'down-payment'})
        assert results == {'computation_key': 'down-payment'}

    def test_matching_setup_imports_the_manual_amounts_at_the_rate(
            self, currency, tax):
        extra = {
            'currency_id': currency.id, 'price_unit': 100.0, 'discount': 0.0,
            'quantity': 2.0, 'rate': 4.0,
            'manual_total_excluded_currency': 200.0,
            'manual_total_excluded': 100.0,
            'manual_tax_amounts': {str(tax.id): {
                'tax_amount_currency': 32.0, 'tax_amount': 16.0,
                'base_amount': 100.0}},
        }
        results = AccountTax._import_base_line_extra_tax_data(
            self._base_line(currency, tax), extra)
        # delta_rate = 2.0 / 4.0: los importes locales se dividen entre él.
        assert results['price_unit'] == 100.0
        assert results['manual_total_excluded_currency'] == 200.0
        assert results['manual_total_excluded'] == 200.0
        assert results['manual_tax_amounts'][str(tax.id)] == {
            'tax_amount_currency': 32.0, 'tax_amount': 32.0,
            'base_amount': 200.0}

    def test_an_edited_setup_drops_the_manual_amounts(self, currency, tax):
        extra = {
            'currency_id': currency.id, 'price_unit': 90.0, 'discount': 0.0,
            'quantity': 2.0,
            'manual_tax_amounts': {str(tax.id): {'tax_amount': 16.0}},
        }
        assert AccountTax._import_base_line_extra_tax_data(
            self._base_line(currency, tax), extra) == {}


class TestPrepareBaseLine:
    """≙ ``_prepare_base_line_for_taxes_computation`` (``:1593-1691``)."""

    def test_from_a_sale_line(self, environment, line, tax):
        base_line = AccountTax._prepare_base_line_for_taxes_computation(
            line, quantity=line.product_uom_qty)
        assert base_line['record'] is line
        assert base_line['id'] == line.id
        assert base_line['product_id'] == line.product
        assert list(base_line['tax_ids']) == [tax]
        assert base_line['price_unit'] == Decimal('10.00')
        assert base_line['quantity'] == Decimal('2')
        assert base_line['special_mode'] is False
        assert base_line['special_type'] is False
        assert base_line['rate'] == 1.0
        assert base_line['sign'] == 1.0
        assert base_line['is_refund'] is False
        assert base_line['manual_tax_amounts'] is None

    def test_from_a_dict_the_private_keys_are_propagated(
            self, environment, currency):
        record = {'price_unit': 5.0, 'quantity': 3.0, 'currency_id': currency,
                  '_ubl_values': {'x': 1}, 'id': 9}
        base_line = AccountTax._prepare_base_line_for_taxes_computation(
            record, special_type='early_payment')
        assert base_line['currency_id'] == currency
        assert base_line['price_unit'] == 5.0
        assert base_line['special_type'] == 'early_payment'
        assert base_line['_ubl_values'] == {'x': 1}
        assert list(base_line['tax_ids']) == []
        assert base_line['product_id'] is None
