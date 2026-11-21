"""``product.pricelist`` y ``product.pricelist.item`` como ``BaseModel``
(etapa 1 del diseño).

≙ ``odoo19c: addons/product/models/product_pricelist.py:9-86`` y
``product_pricelist_item.py:8-269``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-cluster.md``.

*Métrica:* los valores por defecto de moneda y compañía con una empresa
activa, el nombre para mostrar, la copia (con sus reglas y sus grupos de
países), la verificación de empresa al cambiarla, y los cómputos del ítem
(empresa, moneda, margen y su inverso, nombre, obligatoriedad).
*Ciega a:* la selección de reglas y el precio (etapas 3 y 4).
"""
import pytest

from addons.base.models import ResCompany, ResCountryGroup
from addons.base.models.res_currency import ResCurrency
from addons.mail.models import MailThread
from addons.product.models import ProductPricelist, ProductPricelistItem
from exceptions import UserError
from orm.commands import Command
from orm.environments import env, set_current_company, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

PRICELIST = 'product.pricelist'
ITEM = 'product.pricelist.item'


@pytest.fixture
def company():
    euro, _ = ResCurrency.objects.get_or_create(
        name='EUR', defaults={'symbol': '€'})
    company = ResCompany.objects.create(code='ppb-a', name='Compania ppb',
                                        currency=euro)
    set_current_company(company.pk)
    yield company
    set_current_company(None)


def test_the_pricelist_is_a_basemodel_with_a_thread():
    assert issubclass(ProductPricelist, BaseModel)
    assert issubclass(ProductPricelist, MailThread)


def test_the_defaults_come_from_the_active_company(company):
    [pricelist] = env()[PRICELIST].create([{'name': 'PPB Tarifa'}])
    assert pricelist.currency_id == company.currency
    assert pricelist.company_id == company


def test_the_display_name_shows_the_currency(company):
    [pricelist] = env()[PRICELIST].create([{'name': 'PPB Mostrar'}])
    assert pricelist.display_name == 'PPB Mostrar (EUR)'


def test_a_copy_is_named_as_a_copy(company):
    [pricelist] = env()[PRICELIST].create([{'name': 'PPB Original'}])
    assert pricelist.copy().name == 'PPB Original (copy)'


def test_a_copy_keeps_the_rules_and_the_country_groups(company):
    group = ResCountryGroup.objects.create(name='PPB Grupo')
    [pricelist] = env()[PRICELIST].create([{
        'name': 'PPB Con reglas',
        'country_group_ids': [Command.link(group.pk)]}])
    with sudo():
        env()[ITEM].create([{'pricelist_id': pricelist.id,
                             'fixed_price': 3.0}])
        copy = pricelist.copy()
    assert copy.item_ids.mapped('fixed_price') == [3.0]
    assert copy.item_ids != pricelist.item_ids
    assert list(copy.country_group_ids) == [group]


def _template(company, name):
    [template] = env()['product.template'].create(
        [{'name': name, 'company_id': company.pk}])
    return template


def test_changing_the_company_checks_the_rules(company):
    other = ResCompany.objects.create(code='ppb-b', name='Otra ppb')
    [pricelist] = env()[PRICELIST].create([{'name': 'PPB Empresa'}])
    with sudo():
        env()[ITEM].create([{
            'pricelist_id': pricelist.id, 'applied_on': '1_product',
            'product_tmpl_id': _template(company, 'PPB Plantilla').id}])
    with pytest.raises(UserError):
        pricelist.write({'company_id': other.pk})


def test_a_pricelist_without_rules_changes_company(company):
    other = ResCompany.objects.create(code='ppb-c', name='Tercera ppb')
    [pricelist] = env()[PRICELIST].create([{'name': 'PPB Sin reglas'}])
    pricelist.write({'company_id': other.pk})
    assert pricelist.company_id == other


def test_the_item_is_a_basemodel_with_the_source_header():
    assert issubclass(ProductPricelistItem, BaseModel)
    assert ProductPricelistItem._check_company_auto is True
    assert ProductPricelistItem._order == (
        'applied_on, min_quantity desc, categ_id desc, id desc')


def test_the_item_takes_the_company_and_currency_of_its_pricelist(company):
    [pricelist] = env()[PRICELIST].create([{'name': 'PPB Item'}])
    with sudo():
        [item] = env()[ITEM].create([{'pricelist_id': pricelist.id}])
    assert item.company_id == company
    assert item.currency_id == company.currency
    assert item.is_pricelist_required is True
    assert item.display_applied_on == '1_product'


def test_the_item_defaults_to_a_pricelist_of_the_company(company):
    [pricelist] = env()[PRICELIST].create([{'name': 'PPB Defecto'}])
    with sudo():
        [item] = env()[ITEM].create([{}])
    assert item.pricelist_id == pricelist


def test_the_markup_is_the_negated_discount_and_writes_it_back(company):
    with sudo():
        [item] = env()[ITEM].create([{'price_discount': 15.0}])
        assert item.price_markup == -15.0
        item.write({'price_markup': 20.0})
    assert item.price_discount == -20.0


def test_the_name_follows_the_scope(company):
    template = _template(company, 'PPB Nombre')
    with sudo():
        [glob, product] = env()[ITEM].create([
            {},
            {'applied_on': '1_product', 'product_tmpl_id': template.id}])
    assert glob.name == 'All Products'
    assert product.name == template.display_name


def test_the_amounts_are_floats_like_the_source():
    for name in ('fixed_price', 'price_surcharge', 'price_min_margin',
                 'price_max_margin'):
        assert ProductPricelistItem._fields[name].type == 'float', name
