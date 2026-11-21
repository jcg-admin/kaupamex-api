"""Selección de reglas y recursión entre tarifas (etapa 4 del diseño).

≙ ``odoo19c: addons/product/models/product_pricelist.py:90-287``,
``product_pricelist_item.py:661-684`` y los ``_get_contextual_*`` de
``product_template.py:1537-1550`` y ``product_product.py:1167-1193``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-cluster.md``.

*Métrica:* la regla elegida por alcance, cantidad mínima, fecha y rama de
categoría; los cuatro envoltorios; la base ``pricelist`` encadenada; las
tarifas múltiples; el precio antes del descuento; y el precio y descuento
contextuales.
*Ciega a:* las tarifas por país y por cliente (etapa 5).
"""
import datetime

import pytest

from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency
from orm.environments import env, set_current_company, sudo

pytestmark = pytest.mark.django_db

PRICELIST = 'product.pricelist'
ITEM = 'product.pricelist.item'
WHEN = datetime.datetime(2026, 6, 1)


@pytest.fixture(autouse=True)
def company():
    euro, _ = ResCurrency.objects.get_or_create(
        name='EUR', defaults={'symbol': '€'})
    company = ResCompany.objects.create(code='pps-a', name='Compania pps',
                                        currency=euro)
    set_current_company(company.pk)
    with sudo():
        yield company
    set_current_company(None)


def _pricelist(name):
    [pricelist] = env()[PRICELIST].create([{'name': name}])
    return pricelist


def _template(name, **vals):
    [template] = env()['product.template'].create(
        [{'name': name, 'list_price': 100.0, **vals}])
    return template


def _rule(pricelist, **vals):
    [rule] = env()[ITEM].create([{'pricelist_id': pricelist.id, **vals}])
    return rule


def test_the_most_specific_rule_wins():
    pricelist = _pricelist('PPS Especifica')
    template = _template('PPS Producto')
    _rule(pricelist, fixed_price=10.0)
    _rule(pricelist, product_tmpl_id=template.id, fixed_price=20.0)
    assert pricelist._get_product_price(template, 1.0, date=WHEN) == 20.0
    assert pricelist._get_product_price(
        _template('PPS Otro'), 1.0, date=WHEN) == 10.0


def test_the_higher_minimum_quantity_wins_once_reached():
    pricelist = _pricelist('PPS Cantidad')
    template = _template('PPS Volumen')
    _rule(pricelist, fixed_price=10.0)
    _rule(pricelist, fixed_price=8.0, min_quantity=10.0)
    assert pricelist._get_product_price(template, 5.0, date=WHEN) == 10.0
    assert pricelist._get_product_price(template, 10.0, date=WHEN) == 8.0


def test_a_rule_outside_its_dates_is_skipped():
    pricelist = _pricelist('PPS Fechas')
    template = _template('PPS Fecha')
    _rule(pricelist, fixed_price=5.0,
          date_start=datetime.datetime(2027, 1, 1),
          date_end=datetime.datetime(2027, 2, 1))
    assert pricelist._get_product_price(template, 1.0, date=WHEN) == 100.0
    # Ya vencida: sólo la condición sobre ``date_end`` la excluye.
    _rule(pricelist, fixed_price=6.0,
          date_start=datetime.datetime(2025, 1, 1),
          date_end=datetime.datetime(2025, 12, 31))
    assert pricelist._get_product_price(template, 1.0, date=WHEN) == 100.0


def test_a_parent_category_rule_reaches_a_child_category():
    [parent] = env()['product.category'].create([{'name': 'PPS Padre'}])
    [child] = env()['product.category'].create(
        [{'name': 'PPS Hijo', 'parent_id': parent.id}])
    pricelist = _pricelist('PPS Categoria')
    _rule(pricelist, applied_on='2_product_category', categ_id=parent.id,
          fixed_price=33.0)
    template = _template('PPS En hijo', categ_id=child.id)
    assert pricelist._get_product_price(template, 1.0, date=WHEN) == 33.0


def test_without_pricelist_the_list_price_is_returned():
    template = _template('PPS Sin tarifa', list_price=42.0)
    assert env()[PRICELIST]._get_product_price(
        template, 1.0, date=WHEN) == 42.0


def test_the_wrappers_share_the_same_rule():
    pricelist = _pricelist('PPS Envoltorios')
    first, second = _template('PPS Uno'), _template('PPS Dos')
    rule = _rule(pricelist, product_tmpl_id=first.id, fixed_price=7.0)
    assert pricelist._get_product_price_rule(first, 1.0, date=WHEN) == (
        7.0, rule.id)
    assert pricelist._get_product_rule(first, 1.0, date=WHEN) == rule.id
    assert pricelist._get_products_price(first | second, 1.0,
                                         date=WHEN) == {first.id: 7.0,
                                                        second.id: 100.0}


def test_a_rule_based_on_another_pricelist_chains_its_price():
    base = _pricelist('PPS Base')
    derived = _pricelist('PPS Derivada')
    template = _template('PPS Cadena')
    _rule(base, fixed_price=50.0)
    _rule(derived, compute_price='percentage', percent_price=10.0,
          base='pricelist', base_pricelist_id=base.id)
    assert derived._get_product_price(template, 1.0, date=WHEN) == 45.0


def test_several_pricelists_give_one_price_each():
    first, second = _pricelist('PPS M1'), _pricelist('PPS M2')
    template = _template('PPS Multi')
    _rule(first, fixed_price=11.0)
    _rule(second, fixed_price=22.0)
    prices = (first | second)._price_get(template, 1.0, date=WHEN)
    assert prices == {first.id: 11.0, second.id: 22.0}


def test_the_price_before_discount_follows_the_chain():
    base = _pricelist('PPS Antes base')
    derived = _pricelist('PPS Antes derivada')
    template = _template('PPS Antes')
    _rule(base, compute_price='percentage', percent_price=20.0)
    rule = _rule(derived, compute_price='percentage', percent_price=10.0,
                 base='pricelist', base_pricelist_id=base.id)
    currency = derived.currency_id
    assert rule._compute_price_before_discount(
        product=template, quantity=1.0, uom=template.uom_id, date=WHEN,
        currency=currency) == 100.0


def test_the_contextual_price_and_discount_read_the_pricelist():
    pricelist = _pricelist('PPS Contexto')
    template = _template('PPS Contextual')
    _rule(pricelist, compute_price='percentage', percent_price=25.0)
    variant = template.product_variant_ids[:1].with_context(
        pricelist=pricelist.id)
    assert variant._get_contextual_price() == 75.0
    assert variant.get_contextual_price() == 75.0
    assert variant._get_contextual_discount() == pytest.approx(0.25)
    assert template.product_variant_ids[:1]._get_contextual_discount() == 0.0
