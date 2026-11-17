"""El ``Many2many`` de un registro de ``new()`` hacia un comodelo de Django.

≙ ``Many2many.write_new`` y ``_RelationalMulti.convert_to_record``
(``odoo19c: odoo/orm/fields_relational.py:1596-1700, 643``): lo asignado a
un registro nuevo vive en la caché del campo y se lee de ahí. Aquí la
escritura lo dejaba en la caché y la lectura devolvía el conjunto vacío
cuando el comodelo es un modelo de Django (``account.tax``). Lo necesita
``_prepare_add_missing_fields`` de ``purchase.order.line``, que calcula los
impuestos de una línea de ``new()``.
"""
import pytest

import fields

from addons.account.models import AccountTax
from addons.base.models import ResCompany, ResPartner
from orm.environments import env, sudo
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def setup():
    company = ResCompany.objects.create(name='M2M nuevo 0485')
    vendor = ResPartner.objects.create(name='Proveedor M2M 0485')
    tax = AccountTax.objects.create(
        name='IVA M2M 0485', amount=16, type_tax_use='purchase',
        company=company)
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk}])
    return order, tax


def test_an_assigned_set_is_read_back_on_a_new_record(setup):
    order, tax = setup
    line = env()['purchase.order.line'].new(
        {'order_id': order.pk, 'name': 'x'})
    line.tax_ids = AccountTax.objects.filter(pk=tax.pk)
    assert [t.pk for t in line.tax_ids] == [tax.pk]


def test_new_values_are_read_back_on_a_new_record(setup):
    order, tax = setup
    line = env()['purchase.order.line'].new(
        {'order_id': order.pk, 'name': 'x', 'tax_ids': [tax.pk]})
    assert [t.pk for t in line.tax_ids] == [tax.pk]


def test_a_new_record_without_value_reads_empty(setup):
    """Control: sin asignación, el conjunto es vacío."""
    order, _tax = setup
    line = env()['purchase.order.line'].new(
        {'order_id': order.pk, 'name': 'x'})
    assert list(line.tax_ids) == []


def test_a_saved_record_still_reads_its_table(setup):
    """Control: el registro guardado lee la tabla intermedia."""
    order, tax = setup
    [line] = MODELS_BY_NAME['purchase.order.line'].create([{
        'order_id': order.id, 'name': 'x', 'product_qty': 1,
        'price_unit': 1, 'tax_ids': [(6, 0, [tax.pk])]}])
    assert [t.pk for t in line.tax_ids] == [tax.pk]


@pytest.mark.parametrize('form', ['rows', 'ids', 'commands'])
def test_a_list_or_commands_are_read_back_on_a_new_record(setup, form):
    """El ``onchange`` de la fuente asigna filas, ids o comandos; los tres
    llegan a la caché como el ``QuerySet`` del comodelo."""
    order, tax = setup
    line = env()['purchase.order.line'].new(
        {'order_id': order.pk, 'name': 'x'})
    line.tax_ids = {'rows': [tax], 'ids': [tax.pk],
                    'commands': [fields.Command.set([tax.pk])]}[form]
    assert [t.pk for t in line.tax_ids] == [tax.pk]


def test_link_and_unlink_commands_apply_to_the_current_value(setup):
    order, tax = setup
    other = AccountTax.objects.create(
        name='Otro M2M 0485', amount=8, type_tax_use='purchase',
        company=tax.company)
    line = env()['purchase.order.line'].new(
        {'order_id': order.pk, 'name': 'x', 'tax_ids': [tax.pk]})
    line.tax_ids = [fields.Command.link(other.pk),
                    fields.Command.unlink(tax.pk)]
    assert [t.pk for t in line.tax_ids] == [other.pk]
