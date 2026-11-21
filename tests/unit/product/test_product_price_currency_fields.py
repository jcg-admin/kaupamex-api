"""Moneda y precio de la variante y la plantilla como campos calculados.

≙ ``odoo19c: addons/product/models/product_template.py:88-91,257-267`` y
``odoo19c: addons/product/models/product_product.py:25-33,309-335``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-price-currency-fields.md``.

*Métrica:* el valor de ``currency_id``, ``cost_currency_id``,
``price_extra`` y ``lst_price`` leídos del ORM, la conversión por la unidad
del contexto y el inverso de ``lst_price``.
*Ciega a:* la presentación de precios (``min_display_digits``).
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency
from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductTemplateAttributeValue,
)
from addons.uom.models.uom_uom import Uom
from orm.commands import Command
from orm.environments import env, set_current_company

pytestmark = pytest.mark.django_db


def _template(**vals):
    [template] = env()['product.template'].create([
        {'name': 'PPC Plantilla', **vals}])
    return template


def _variant_with_extra(extra):
    color = ProductAttribute.objects.create(name='PPC Color')
    gold = ProductAttributeValue.objects.create(attribute_id=color, name='Oro')
    template = _template(list_price=Decimal('100.00'), attribute_line_ids=[
        Command.create({'attribute_id': color.pk,
                        'value_ids': [Command.set([gold.pk])]})])
    ptav = ProductTemplateAttributeValue.objects.get(
        product_tmpl_id=template.id, product_attribute_value_id=gold)
    ptav.write({'price_extra': extra})
    return template.product_variant_ids


def test_the_currency_is_the_one_of_the_product_company():
    ResCompany.objects.create(code='ppc-p', name='Compania ppc principal')
    euro, _ = ResCurrency.objects.get_or_create(
        name='EUR', defaults={'symbol': '€'})
    company = ResCompany.objects.create(code='ppc-a', name='Compania ppc',
                                        currency=euro)
    assert ResCompany.get_main_company().currency != euro
    template = _template(company_id=company.pk)
    assert template.currency_id == company.currency
    assert template.product_variant_ids.currency_id == company.currency


def test_without_company_the_currency_is_the_main_company_one():
    ResCompany.objects.create(code='ppc-m', name='Compania ppc m')
    template = _template()
    main = ResCompany.get_main_company()
    assert template.currency_id == main.currency


def test_without_company_the_cost_currency_is_the_active_company_one():
    company = ResCompany.objects.create(code='ppc-e', name='Compania ppc e')
    template = _template()
    set_current_company(company.pk)
    try:
        assert template.cost_currency_id == company.currency
        assert template.product_variant_ids.cost_currency_id == (
            company.currency)
    finally:
        set_current_company(None)


def test_the_extra_is_the_sum_of_the_attribute_extras():
    variant = _variant_with_extra(Decimal('30.00'))
    assert variant.price_extra == Decimal('30.00')
    assert variant.lst_price == Decimal('130.00')


def test_the_price_follows_the_unit_of_the_context():
    variant = _variant_with_extra(Decimal('30.00'))
    dozen = Uom.objects.create(name='PPC Docena', relative_factor=12.0,
                               relative_uom_id=variant.uom_id)
    in_dozens = variant.with_context(uom=dozen.pk)
    expected = variant.uom_id._compute_price(Decimal('100.00'), dozen)
    assert in_dozens.lst_price == expected + Decimal('30.00')


def test_writing_the_sales_price_moves_the_template_price():
    variant = _variant_with_extra(Decimal('30.00'))
    variant.write({'lst_price': Decimal('150.00')})
    assert variant.product_tmpl_id.list_price == Decimal('120.00')
