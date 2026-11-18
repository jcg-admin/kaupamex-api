"""El vínculo de ``purchase`` con las facturas.

≙ ``odoo19c: addons/purchase/models/account_invoice.py:523-530``,
``purchase_order.py:70-75,125-126,641-649`` y ``purchase_order_line.py:56``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-invoice-link.md``.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import AccountJournal, AccountMove, AccountMoveLine
from addons.base.models import ResCompany, ResPartner
from exceptions import UserError
from orm.environments import sudo
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    return ResCompany.objects.create(name='Compras IL')


def _order(company):
    vendor = ResPartner.objects.create(name='Proveedor IL')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk}])
    [line] = MODELS_BY_NAME['purchase.order.line'].create(
        [{'order_id': order.id, 'name': 'Eleke',
          'price_unit': Decimal('10')}])
    return order, line


def _bill(company, line, state='draft'):
    journal = AccountJournal.objects.create(
        name='Compras IL', code='BILIL', type='purchase', company=company)
    move = AccountMove.objects.create(
        date=timezone.now().date(), journal=journal, company=company,
        state=state)
    AccountMoveLine.objects.create(
        move=move, debit=Decimal('10'), purchase_line_id=line)
    return move


def test_the_bill_line_reaches_the_purchase_line(company):
    order, line = _order(company)
    move = _bill(company, line)
    [bill_line] = AccountMoveLine.objects.filter(move=move)
    assert line.invoice_lines.ids == [bill_line.pk]
    assert bill_line.purchase_order_id.id == order.id
    assert bill_line.is_downpayment is False


def test_the_order_lists_its_bills(company):
    order, line = _order(company)
    move = _bill(company, line)
    order.invalidate_recordset()
    assert [m.pk for m in order.invoice_ids] == [move.pk]
    assert order.invoice_count == 1


def test_a_posted_bill_blocks_the_cancellation(company):
    order, line = _order(company)
    _bill(company, line, state='posted')
    with pytest.raises(UserError):
        order.button_cancel()
    order.invalidate_recordset()
    assert order.state == 'draft'


def test_draft_bills_do_not_block_the_cancellation(company):
    order, line = _order(company)
    _bill(company, line)
    order.button_cancel()
    assert order.state == 'cancel'


def test_moving_a_bill_line_updates_both_orders(company):
    first, first_line = _order(company)
    second, second_line = _order(company)
    move = _bill(company, first_line)
    [bill_line] = AccountMoveLine.objects.filter(move=move)
    assert first.invoice_count == 1
    bill_line.purchase_line_id = second_line
    bill_line.save()
    assert first.invoice_count == 0
    assert second.invoice_count == 1
    bill_line.delete()
    assert second.invoice_count == 0


def test_deleting_the_purchase_line_empties_the_link(company):
    order, line = _order(company)
    move = _bill(company, line)
    MODELS_BY_NAME['purchase.order.line'].objects.filter(pk=line.id).delete()
    [bill_line] = AccountMoveLine.objects.filter(move=move)
    assert not bill_line.purchase_line_id
