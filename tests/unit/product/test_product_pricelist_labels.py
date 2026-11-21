"""Etiquetas, ``onchange``, tarifa por país, importación y acción de la
tarifa (etapa 5a del diseño).

≙ ``odoo19c: addons/product/models/product_pricelist_item.py:159-163``,
``:198-311``, ``:383-477`` y ``odoo19c: addons/product/models/
product_pricelist.py:288-330``, ``:377-414``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-cluster.md``.

*Métrica:* el texto de ``price`` y ``rule_tip`` en los tres modos, los nueve
``onchange`` sobre registros de ``new()``, la tarifa por país con su
respaldo, la plantilla de importación y la acción del informe.
*Ciega a:* la tarifa por cliente (sucesora
``product-partner-pricelist-0397``).
"""
import datetime

import pytest

from addons.base.models import ResCompany
from addons.base.models.res_country import ResCountry
from addons.base.models.res_country_group import ResCountryGroup
from addons.base.models.res_currency import ResCurrency
from exceptions import ValidationError
from orm.environments import env, set_current_company, sudo
from tools.misc import format_amount, formatLang

pytestmark = pytest.mark.django_db

PRICELIST = 'product.pricelist'
ITEM = 'product.pricelist.item'


@pytest.fixture(autouse=True)
def company():
    euro, _ = ResCurrency.objects.get_or_create(
        name='EUR', defaults={'symbol': '€'})
    company = ResCompany.objects.create(code='ppl-a', name='Compania ppl',
                                        currency=euro)
    set_current_company(company.pk)
    with sudo():
        yield company
    set_current_company(None)


def _item(**vals):
    [item] = env()[ITEM].create([{'pricelist_id': False, **vals}])
    return item


# === etiquetas ============================================================

def test_a_fixed_rule_shows_its_formatted_amount():
    item = _item(compute_price='fixed', fixed_price=10.0)
    assert item.price == formatLang(item.env, 10.0, dp="Product Price",
                                    currency_obj=item.currency_id)


def test_a_percentage_rule_names_its_base():
    assert _item(compute_price='percentage',
                 percent_price=10.0).price == (
        "10 % discount on sales price")
    [base, derived] = env()[PRICELIST].create(
        [{'name': 'PPL Base'}, {'name': 'PPL Derivada'}])
    item = _item(compute_price='percentage', percent_price=12.5,
                 base='pricelist', base_pricelist_id=base.id,
                 pricelist_id=derived.id)
    assert item.price == f"12.5 % discount on {base.display_name}"


def test_a_formula_rule_shows_its_discount_and_fee():
    item = _item(compute_price='formula', price_discount=15.0,
                 price_surcharge=2.0)
    fee = format_amount(item.env, 2.0, currency=item.currency_id)
    assert item.price == f"15 % discount on sales price + {fee} extra fee"
    cost = _item(compute_price='formula', base='standard_price',
                 price_markup=20.0)
    assert cost.price == "20 % markup on product cost "


def test_the_rule_tip_explains_the_formula_only():
    assert not _item(compute_price='fixed').rule_tip
    tip = _item(compute_price='formula', price_discount=10.0).rule_tip
    assert tip.startswith("Sales Price with a 10 % discount")


def test_get_integer_keeps_fractions():
    item = env()[ITEM]
    assert item._get_integer(10.0) == 10
    assert item._get_integer(10.5) == 10.5


# === onchange =============================================================

def test_changing_the_base_resets_discount_and_markup():
    item = env()[ITEM].new({'price_discount': 5.0})
    item._onchange_base()
    assert item.price_discount == 0.0
    assert item.price_markup == 0.0


def test_changing_the_computation_clears_the_other_modes():
    item = env()[ITEM].new({'compute_price': 'percentage',
                            'fixed_price': 9.0, 'percent_price': 4.0,
                            'price_surcharge': 3.0})
    item._onchange_compute_price()
    assert item.fixed_price == 0.0
    assert item.percent_price == 4.0
    assert item.price_surcharge == 0.0


def test_a_percentage_rule_takes_the_base_from_the_other_pricelist():
    [base] = env()[PRICELIST].create([{'name': 'PPL Onchange'}])
    item = env()[ITEM].new({'compute_price': 'percentage',
                            'base_pricelist_id': base.id})
    item._onchange_base_pricelist_id()
    assert item.base == 'pricelist'


def test_display_applied_on_sets_the_scope():
    [category] = env()['product.category'].create([{'name': 'PPL Cat'}])
    item = env()[ITEM].new({'display_applied_on': '2_product_category',
                            'categ_id': category.id})
    item._onchange_display_applied_on()
    assert item.applied_on == '2_product_category'
    assert env()[ITEM].new({})._onchange_display_applied_on() is None


def test_a_variant_sets_its_template_and_scope():
    [template] = env()['product.template'].create([{'name': 'PPL Var'}])
    variant = template.product_variant_ids[:1]
    item = env()[ITEM].with_context(default_applied_on='1_product').new(
        {'product_id': variant.id})
    item._onchange_product_id()
    assert item.product_tmpl_id == template
    assert item.applied_on == '0_product_variant'


def test_a_new_template_drops_a_foreign_variant():
    [first, second] = env()['product.template'].create(
        [{'name': 'PPL Uno'}, {'name': 'PPL Dos'}])
    item = env()[ITEM].new({
        'product_tmpl_id': second.id,
        'product_id': first.product_variant_ids[:1].id})
    item._onchange_product_tmpl_id()
    assert not item.product_id


def test_the_rule_content_decides_the_scope():
    [template] = env()['product.template'].create([{'name': 'PPL Cont'}])
    item = env()[ITEM].new({'product_tmpl_id': template.id})
    item._onchange_rule_content()
    assert item.applied_on == '1_product'


def test_a_negative_rounding_is_refused():
    with pytest.raises(ValidationError):
        env()[ITEM].new({'price_round': -1.0})._onchange_price_round()


def test_the_validity_period_is_checked_on_change():
    moment = datetime.datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        env()[ITEM].new({'date_start': moment,
                         'date_end': moment})._onchange_validity_period()


# === tarifa por país, importación y acción ================================

def test_a_country_gets_the_pricelist_of_its_group(company):
    country = ResCountry.objects.create(name='PPL Pais', code='PZ')
    group = ResCountryGroup.objects.create(name='PPL Grupo')
    group.country_ids.add(country)
    [fallback, grouped] = env()[PRICELIST].create([
        {'name': 'PPL Respaldo', 'sequence': 1},
        {'name': 'PPL Grupo', 'sequence': 2,
         'country_group_ids': [(4, group.pk)]}])
    result = env()[PRICELIST]._get_country_pricelist_multi([country.pk])
    assert result[country.pk] == grouped
    assert result[False] == fallback


def test_the_import_template_and_the_report_action():
    [template] = env()[PRICELIST].get_import_templates()
    assert template['template'] == '/product/static/xls/product_pricelist.xls'
    [pricelist] = env()[PRICELIST].create([{'name': 'PPL Informe'}])
    action = pricelist.action_open_pricelist_report()
    assert action['tag'] == 'generate_pricelist_report'
