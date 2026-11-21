"""Integridad de ``product.pricelist.item`` y ``product.pricelist`` (etapa
2 del diseño).

≙ ``odoo19c: addons/product/models/product_pricelist_item.py:316-381``
(restricciones), ``:479-522`` (``create`` y ``write``) y
``odoo19c: addons/product/models/product_pricelist.py:393-405`` (guarda de
borrado). Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/product-pricelist-cluster.md``.

*Métrica:* cada restricción con un caso que la viola y uno válido, la
recursión directa e indirecta, la deducción e inferencia de ``create``, la
limpieza de alcance en ``create``/``write`` y la guarda de borrado.
*Ciega a:* la selección de reglas y el precio (etapas 3 y 4).
"""
import datetime

import pytest

from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency
from exceptions import UserError, ValidationError
from orm.environments import env, set_current_company, sudo

pytestmark = pytest.mark.django_db

PRICELIST = 'product.pricelist'
ITEM = 'product.pricelist.item'


@pytest.fixture(autouse=True)
def company():
    euro, _ = ResCurrency.objects.get_or_create(
        name='EUR', defaults={'symbol': '€'})
    company = ResCompany.objects.create(code='ppi-a', name='Compania ppi',
                                        currency=euro)
    set_current_company(company.pk)
    with sudo():
        yield company
    set_current_company(None)


def _pricelist(name):
    [pricelist] = env()[PRICELIST].create([{'name': name}])
    return pricelist


def _template(name):
    [template] = env()['product.template'].create([{'name': name}])
    return template


def _item(**vals):
    [item] = env()[ITEM].create([vals])
    return item


# === restricciones ========================================================

def test_a_pricelist_base_needs_its_pricelist():
    with pytest.raises(ValidationError):
        _item(base='pricelist', pricelist_id=_pricelist('PPI base').id)


def test_a_pricelist_base_with_its_pricelist_is_valid():
    other = _pricelist('PPI otra')
    item = _item(base='pricelist', base_pricelist_id=other.id,
                 pricelist_id=_pricelist('PPI derivada').id)
    assert item.base_pricelist_id == other


def test_a_rule_cannot_be_based_on_its_own_pricelist():
    pricelist = _pricelist('PPI propia')
    with pytest.raises(ValidationError, match='Recursive'):
        _item(base='pricelist', base_pricelist_id=pricelist.id,
              pricelist_id=pricelist.id)


def test_an_indirect_cycle_is_detected():
    first, second = _pricelist('PPI uno'), _pricelist('PPI dos')
    _item(base='pricelist', base_pricelist_id=second.id,
          pricelist_id=first.id)
    with pytest.raises(ValidationError, match='Recursive'):
        _item(base='pricelist', base_pricelist_id=first.id,
              pricelist_id=second.id)


def test_a_chain_without_a_cycle_is_valid():
    first, second, third = (_pricelist('PPI a'), _pricelist('PPI b'),
                            _pricelist('PPI c'))
    _item(base='pricelist', base_pricelist_id=second.id,
          pricelist_id=first.id)
    item = _item(base='pricelist', base_pricelist_id=third.id,
                 pricelist_id=second.id)
    assert item.base_pricelist_id == third


def test_the_end_date_must_come_after_the_start():
    moment = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    with pytest.raises(ValidationError):
        _item(date_start=moment, date_end=moment)
    item = _item(date_start=moment,
                 date_end=moment + datetime.timedelta(days=1))
    assert item.date_end > item.date_start


def test_the_minimum_margin_cannot_exceed_the_maximum():
    with pytest.raises(ValidationError):
        _item(price_min_margin=5.0, price_max_margin=1.0)
    assert _item(price_min_margin=1.0, price_max_margin=5.0)


def test_a_scoped_rule_needs_its_target():
    item = _item()
    with pytest.raises(ValidationError):
        item.write({'applied_on': '2_product_category'})


# === create y write =======================================================

def test_create_deduces_the_template_and_the_scope_from_a_variant():
    template = _template('PPI Variante')
    variant = template.product_variant_ids[:1]
    item = _item(product_id=variant.id)
    assert item.product_tmpl_id == template
    assert item.applied_on == '0_product_variant'


def test_create_infers_the_scope_from_a_template():
    item = _item(product_tmpl_id=_template('PPI Plantilla').id)
    assert item.applied_on == '1_product'


def test_create_clears_the_targets_of_a_global_rule():
    item = _item(applied_on='3_global',
                 product_tmpl_id=_template('PPI Global').id)
    assert not item.product_tmpl_id


def test_write_clears_the_targets_outside_the_new_scope():
    template = _template('PPI Escritura')
    item = _item(product_tmpl_id=template.id)
    item.write({'applied_on': '3_global'})
    assert not item.product_tmpl_id


# === guarda de borrado ====================================================

def test_a_pricelist_used_as_a_base_cannot_be_deleted():
    base, derived = _pricelist('PPI cimiento'), _pricelist('PPI encima')
    _item(base='pricelist', base_pricelist_id=base.id,
          pricelist_id=derived.id)
    with pytest.raises(UserError):
        base.unlink()


def test_deleting_both_pricelists_together_is_allowed():
    base, derived = _pricelist('PPI juntos a'), _pricelist('PPI juntos b')
    _item(base='pricelist', base_pricelist_id=base.id,
          pricelist_id=derived.id)
    (derived | base).unlink()
    assert not env()[PRICELIST].search(
        [('id', 'in', [base.id, derived.id])])
