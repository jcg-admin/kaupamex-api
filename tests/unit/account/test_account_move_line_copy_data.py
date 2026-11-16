"""``copy_data`` de ``account.move.line`` y sus campos de negocio.

≙ ``odoo19c: addons/account/models/account_move_line.py:2071-2086,3765-3766``,
``purchase/models/account_invoice.py:532-535`` y
``sale/models/account_move_line.py:36-39``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
account-copy-data-business-fields.md``.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import AccountJournal, AccountMove, AccountMoveLine
from addons.base.models import ResCompany, ResPartner
from orm.environments import Environment, sudo
from orm.registry import MODELS_BY_NAME
from orm.utils import SUPERUSER_ID
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _move(move_type='out_invoice'):
    company = ResCompany.objects.create(name='Copia %s' % move_type)
    journal = AccountJournal.objects.create(
        name='Diario', code='CPY', type='sale', company=company)
    return AccountMove.objects.create(
        date=timezone.now().date(), journal=journal, company=company,
        move_type=move_type)


def _line(move, display_type, **values):
    return AccountMoveLine.objects.create(
        move=move, debit=Decimal('5.00'), credit=Decimal('0.00'),
        name='Línea', display_type=display_type, **values)


def test_an_invoice_product_line_copies_without_balance():
    vals = _line(_move(), 'product').copy_data()
    assert 'balance' not in vals
    assert vals['name'] == 'Línea'


def test_a_product_line_of_an_entry_keeps_its_balance():
    assert 'balance' in _line(_move('entry'), 'product').copy_data()


def test_a_section_copies_without_balance_nor_account():
    vals = _line(_move(), 'line_section').copy_data()
    assert 'balance' not in vals and 'account_id' not in vals


def test_an_invoice_payment_term_line_copies_without_name():
    assert 'name' not in _line(_move(), 'payment_term').copy_data()


def _purchase_line():
    company = ResCompany.objects.create(name='Compra copia')
    vendor = ResPartner.objects.create(name='Proveedor copia')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    product = make_product(name='Insumo copia')
    [line] = MODELS_BY_NAME['purchase.order.line'].create([{
        'order_id': order.id, 'name': 'Insumo',
        'price_unit': Decimal('1.00'), 'product_id': product.pk}])
    return line


def test_without_the_context_the_business_fields_stay_behind():
    line = _line(_move('in_invoice'), 'product',
                 purchase_line_id=_purchase_line())
    vals = line.copy_data()
    assert 'purchase_line_id' not in vals
    assert 'sale_line_ids' not in vals


def test_with_include_business_fields_the_purchase_line_is_copied():
    purchase_line = _purchase_line()
    line = _line(_move('in_invoice'), 'product',
                 purchase_line_id=purchase_line)
    with Environment('default', SUPERUSER_ID,
                     {'include_business_fields': True}):
        vals = line.copy_data()
    assert vals['purchase_line_id'] == purchase_line.id


def test_with_include_business_fields_the_sale_lines_are_set():
    line = _line(_move(), 'product')
    with Environment('default', SUPERUSER_ID,
                     {'include_business_fields': True}):
        vals = line.copy_data()
    assert vals['sale_line_ids'] == [(6, None, [])]

