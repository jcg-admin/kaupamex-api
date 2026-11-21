"""``product.combo`` y ``product.combo.item`` como ``BaseModel``, completos.

≙ ``odoo19c: addons/product/models/product_combo.py``,
``odoo19c: addons/product/models/product_combo_item.py`` y las dos
restricciones de ``product.template`` sobre ``combo_ids``
(``odoo19c: addons/product/models/product_template.py:489-507``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-combo-basemodel.md``.

*Métrica:* las restricciones al crear y escribir por el ORM, los calculados
leídos del ORM y la compañía precalculada de la opción.
*Ciega a:* la presentación (``min_display_digits``) y el ``domain`` del
selector de opciones, que es interfaz.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency
from addons.product.models import ProductCombo, ProductComboItem
from exceptions import UserError, ValidationError
from orm.commands import Command
from orm.environments import env
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def _variant(name, **vals):
    [template] = env()['product.template'].create([{'name': name, **vals}])
    return template.product_variant_ids


def _combo(name, *variants, **vals):
    [combo] = env()['product.combo'].create([{
        'name': name,
        'combo_item_ids': [Command.create({'product_id': variant.id})
                           for variant in variants],
        **vals,
    }])
    return combo


def test_both_models_are_basemodels():
    assert issubclass(ProductCombo, BaseModel)
    assert issubclass(ProductComboItem, BaseModel)


def test_a_choice_needs_at_least_one_option():
    with pytest.raises(ValidationError):
        _combo('PCB Vacia')


def test_a_choice_cannot_offer_the_same_product_twice():
    water = _variant('PCB Agua', list_price=Decimal('10.00'))
    with pytest.raises(ValidationError):
        _combo('PCB Doble', water, water)


def test_an_option_cannot_be_a_combo():
    soda = _variant('PCB Refresco')
    menu_choice = _combo('PCB Bebida menu', soda)
    menu = _variant('PCB Menu', type='combo',
                    combo_ids=[Command.set([menu_choice.id])])
    with pytest.raises(ValidationError):
        _combo('PCB Anidada', menu)


def test_the_count_and_the_base_price_read_the_options():
    ResCompany.objects.create(code='pcb-bp', name='Compania pcb bp')
    water = _variant('PCB Agua2', list_price=Decimal('10.00'))
    soda = _variant('PCB Refresco2', list_price=Decimal('25.00'))
    combo = _combo('PCB Bebidas', water, soda)
    assert combo.combo_item_count == 2
    assert combo.base_price == Decimal('10.00')


def test_the_currency_falls_back_to_the_main_company():
    ResCompany.objects.create(code='pcb-m', name='Compania pcb principal')
    combo = _combo('PCB Moneda', _variant('PCB Te'))
    assert combo.currency_id == ResCompany.get_main_company().currency


def test_the_currency_is_the_one_of_the_choice_company():
    ResCompany.objects.create(code='pcb-p', name='Compania pcb p')
    euro, _ = ResCurrency.objects.get_or_create(
        name='EUR', defaults={'symbol': '€'})
    company = ResCompany.objects.create(code='pcb-e', name='Compania pcb e',
                                        currency=euro)
    combo = _combo('PCB Euro', _variant('PCB Cafe'), company_id=company.pk)
    assert combo.currency_id == euro


def test_an_option_takes_the_company_of_its_choice():
    company = ResCompany.objects.create(code='pcb-c', name='Compania pcb c')
    combo = _combo('PCB Compania', _variant('PCB Jugo'),
                   company_id=company.pk)
    assert combo.combo_item_ids.company_id == company


def test_an_option_of_another_company_is_refused():
    company = ResCompany.objects.create(code='pcb-a', name='Compania pcb a')
    other = ResCompany.objects.create(code='pcb-b', name='Compania pcb b')
    foreign = _variant('PCB Ajeno', company_id=other.pk)
    with pytest.raises(UserError):
        _combo('PCB Ajena', foreign, company_id=company.pk)


def test_a_combo_product_needs_a_choice():
    with pytest.raises(ValidationError):
        _variant('PCB Menu vacio', type='combo')


def test_a_sellable_combo_only_offers_sellable_products():
    hidden = _variant('PCB Oculto', sale_ok=False)
    choice = _combo('PCB Eleccion oculta', hidden)
    with pytest.raises(ValidationError):
        _variant('PCB Menu vendible', type='combo', sale_ok=True,
                 combo_ids=[Command.set([choice.id])])


def test_the_sequence_is_not_copied():
    combo = _combo('PCB Copia', _variant('PCB Pan'), sequence=7)
    assert combo.copy().sequence == 10
