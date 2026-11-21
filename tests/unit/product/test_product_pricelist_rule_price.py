"""El precio de una regla de tarifa (etapa 3 del diseño).

≙ ``odoo19c: addons/product/models/product_pricelist_item.py:526-659``
(``_is_applicable_for``, ``_compute_price``, ``_compute_base_price``) y
``_price_compute`` de ``product_template.py:737-768`` y
``product_product.py:1101-1130``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-cluster.md``.

*Métrica:* la aplicabilidad por cantidad, categoría, plantilla y variante;
los tres modos de cálculo con el orden de la fórmula; la conversión de unidad
y de moneda; y la regla vacía, que devuelve el precio base.
*Ciega a:* la base ``pricelist`` y la selección de reglas (etapa 4).
"""
import datetime
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResCurrencyRate
from addons.base.models.res_currency import ResCurrency
from orm.environments import env, set_current_company, sudo

pytestmark = pytest.mark.django_db

ITEM = 'product.pricelist.item'


@pytest.fixture(autouse=True)
def company():
    euro, _ = ResCurrency.objects.get_or_create(
        name='EUR', defaults={'symbol': '€'})
    company = ResCompany.objects.create(code='prp-a', name='Compania prp',
                                        currency=euro)
    set_current_company(company.pk)
    with sudo():
        yield company
    set_current_company(None)


def _uom(name, factor=1.0, relative=None):
    [uom] = env()['uom.uom'].create([{
        'name': name, 'relative_factor': factor,
        'relative_uom_id': relative.id if relative else False}])
    return uom


def _template(name, **vals):
    [template] = env()['product.template'].create([{'name': name, **vals}])
    return template


def _rule(**vals):
    [rule] = env()[ITEM].create([{'pricelist_id': False, **vals}])
    return rule


def _price(rule, product, quantity=1.0, uom=None, currency=None):
    return rule._compute_price(product, quantity, uom or product.uom_id,
                               datetime.datetime(2026, 6, 1),
                               currency=currency)


# === _is_applicable_for ===================================================

def test_the_minimum_quantity_gates_the_rule():
    product = _template('PRP Cantidad').product_variant_ids[:1]
    rule = _rule(min_quantity=5.0)
    assert not rule._is_applicable_for(product, 4.0)
    assert rule._is_applicable_for(product, 5.0)


def test_a_category_rule_reaches_its_branch_only():
    [root, other] = env()['product.category'].create(
        [{'name': 'PRP Raiz'}, {'name': 'PRP Otra'}])
    [child] = env()['product.category'].create(
        [{'name': 'PRP Hija', 'parent_id': root.id}])
    rule = _rule(applied_on='2_product_category', categ_id=root.id)
    assert rule._is_applicable_for(
        _template('PRP Rama', categ_id=child.id), 1.0)
    assert not rule._is_applicable_for(
        _template('PRP Fuera', categ_id=other.id), 1.0)


def test_a_product_rule_matches_its_template_and_its_variants():
    template = _template('PRP Producto')
    rule = _rule(product_tmpl_id=template.id)
    assert rule._is_applicable_for(template, 1.0)
    assert rule._is_applicable_for(template.product_variant_ids[:1], 1.0)
    assert not rule._is_applicable_for(_template('PRP Ajeno'), 1.0)


def test_a_variant_rule_accepts_a_single_variant_template():
    template = _template('PRP Variante')
    variant = template.product_variant_ids[:1]
    rule = _rule(product_id=variant.id)
    assert rule._is_applicable_for(variant, 1.0)
    assert rule._is_applicable_for(template, 1.0)
    assert not rule._is_applicable_for(
        _template('PRP Otra variante').product_variant_ids[:1], 1.0)


# === _compute_price =======================================================

def test_a_fixed_rule_converts_its_price_to_the_requested_unit():
    unit = _uom('PRP Unidad')
    dozen = _uom('PRP Docena', 12.0, unit)
    product = _template('PRP Fijo', uom_id=unit.id).product_variant_ids[:1]
    rule = _rule(compute_price='fixed', fixed_price=1.0)
    assert _price(rule, product, uom=dozen) == pytest.approx(12.0)


def test_a_percentage_rule_discounts_the_list_price():
    product = _template('PRP Porcentaje', list_price=200.0)
    rule = _rule(compute_price='percentage', percent_price=10.0)
    assert _price(rule, product) == pytest.approx(180.0)


def test_the_formula_rounds_before_the_surcharge_and_bounds_by_the_base():
    product = _template('PRP Formula', list_price=100.0)
    rule = _rule(compute_price='formula', price_discount=12.0,
                 price_round=5.0, price_surcharge=0.99)
    # 100 - 12 % = 88 -> redondeo a 5 = 90 -> + 0.99
    assert _price(rule, product) == pytest.approx(90.99)
    bounded = _rule(compute_price='formula', price_discount=50.0,
                    price_min_margin=10.0, price_max_margin=20.0)
    # 50 queda por debajo de la base + 10: el margen se mide contra la base
    assert _price(bounded, product) == pytest.approx(110.0)


def test_a_cost_based_formula_marks_up_instead_of_discounting():
    product = _template('PRP Coste', standard_price=40.0)
    rule = _rule(compute_price='formula', base='standard_price',
                 price_markup=25.0)
    assert _price(rule, product) == pytest.approx(50.0)


def test_an_empty_rule_gives_the_base_price():
    product = _template('PRP Vacia', list_price=73.0)
    assert _price(env()[ITEM], product) == pytest.approx(73.0)


def test_the_base_price_is_converted_to_the_requested_currency(company):
    dollar, _ = ResCurrency.objects.get_or_create(
        name='USD', defaults={'symbol': '$'})
    ResCurrencyRate.objects.create(currency=dollar,
                                   name=datetime.date(2026, 1, 1),
                                   rate=Decimal('2.0'))
    product = _template('PRP Moneda', list_price=10.0)
    rule = _rule(compute_price='percentage', percent_price=0.0)
    assert _price(rule, product, currency=dollar) == pytest.approx(20.0)


def test_the_template_price_compute_reads_the_requested_field():
    template = _template('PRP Plantilla', list_price=30.0,
                         standard_price=12.0)
    assert template._price_compute('list_price')[template.id] == 30.0
    assert template._price_compute('standard_price')[template.id] == 12.0
