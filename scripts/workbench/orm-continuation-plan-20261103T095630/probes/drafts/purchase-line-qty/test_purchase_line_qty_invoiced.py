"""La cantidad facturada de la línea de compra.

≙ ``odoo19c: addons/purchase/models/purchase_order_line.py:56,61-63,
68-80,164-211,280-285,571-587``. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/purchase-order-line-port.md``
(unidad 3).
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountJournal, AccountMove, AccountMoveLine, AccountTax)
from addons.base.models import ResCompany, ResPartner
from addons.uom.models import Uom
from orm.environments import context_scope, sudo
from orm.registry import MODELS_BY_NAME
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db
LINE = 'purchase.order.line'


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    return ResCompany.objects.create(name='Compras facturado 0122')


def _line(company, qty='10', price='10', method='purchase', **values):
    vendor = ResPartner.objects.create(name='Proveedor facturado 0122')
    [order] = MODELS_BY_NAME['purchase.order'].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    product = values.pop('product', None) or make_product(
        name='Insumo facturado', purchase_method=method)
    [line] = MODELS_BY_NAME[LINE].create([{
        'order_id': order.id, 'name': 'Insumo', 'product_id': product.pk,
        'product_qty': Decimal(qty), 'price_unit': Decimal(price),
        **values}])
    return line


def _bill(company, line, quantity, move_type='in_invoice', state='posted',
          invoice_date=None, uom=None, payment_state=None):
    journal = AccountJournal.objects.create(
        name='Compras', code=f'B{AccountJournal.objects.count()}',
        type='purchase', company=company)
    values = {'date': timezone.now().date(), 'journal': journal,
              'company': company, 'state': state, 'move_type': move_type,
              'invoice_date': invoice_date}
    if payment_state:
        values['payment_state'] = payment_state
    move = AccountMove.objects.create(**values)
    AccountMoveLine.objects.create(
        move=move, debit=Decimal('1'), quantity=Decimal(quantity),
        product_uom_id=uom or line.product_uom_id or line.product_id.uom,
        purchase_line_id=line)
    line.invalidate_recordset()
    return move


def test_the_fields_of_the_unit():
    model = MODELS_BY_NAME[LINE]
    for name in ('qty_invoiced', 'qty_to_invoice'):
        assert model._meta.get_field(name).decimal_places == 4, name
        assert model._fields[name].store is True, name
    for name in ('qty_invoiced_at_date', 'amount_to_invoice_at_date'):
        assert model._fields[name].store is False, name


def test_a_bill_adds_and_a_refund_subtracts(company):
    line = _line(company)
    _bill(company, line, '3')
    _bill(company, line, '1', move_type='in_refund')
    assert line._prepare_qty_invoiced()[line] == Decimal('2')


def test_a_cancelled_bill_does_not_count_unless_legacy(company):
    line = _line(company)
    _bill(company, line, '3', state='cancel')
    assert line._prepare_qty_invoiced()[line] == 0
    _bill(company, line, '2', state='cancel',
          payment_state='invoicing_legacy')
    assert line._prepare_qty_invoiced()[line] == Decimal('2')


def test_the_bill_unit_is_converted_to_the_line_unit(company):
    unit = Uom.objects.create(name='Units F3', relative_factor=1.0)
    dozen = Uom.objects.create(name='Dozen F3', relative_factor=12,
                               relative_uom_id=unit)
    product = make_product(name='Insumo F3', uom=unit)
    line = _line(company, product=product, product_uom_id=unit.pk)
    _bill(company, line, '1', uom=dozen)
    assert line._prepare_qty_invoiced()[line] == Decimal('12')


def test_qty_to_invoice_follows_the_purchase_method(company):
    ordered = _line(company, method='purchase')
    received = _line(company, method='receive')
    for line in (ordered, received):
        line.order_id.button_confirm()
        line.write({'qty_received': Decimal('4')})
        _bill(company, line, '1')
        line.flush_recordset()
        line.invalidate_recordset()
    assert ordered.qty_invoiced == Decimal('1')
    assert ordered.qty_to_invoice == Decimal('9')
    assert received.qty_to_invoice == Decimal('3')


def test_a_draft_order_has_nothing_to_invoice(company):
    line = _line(company)
    _bill(company, line, '1')
    line.flush_recordset()
    line.invalidate_recordset()
    assert line.qty_invoiced == Decimal('1')
    assert line.qty_to_invoice == 0


def test_the_accrual_date_filters_the_bills(company):
    line = _line(company)
    today = timezone.localdate()
    _bill(company, line, '2', invoice_date=today - datetime.timedelta(days=5))
    _bill(company, line, '3', invoice_date=today)
    accrual = (today - datetime.timedelta(days=1)).isoformat()
    with context_scope(accrual_entry_date=accrual):
        assert len(line._get_invoice_lines()) == 1
        assert line.qty_invoiced_at_date == Decimal('2')


def test_the_gross_price_unit(company):
    tax = AccountTax.objects.create(
        name='IVA 16', amount=Decimal('16'), company=company,
        type_tax_use='purchase', price_include=True)
    line = _line(company, price='116', discount=Decimal('10'),
                 tax_ids=[(6, 0, [tax.pk])])
    assert line._get_gross_price_unit() == pytest.approx(
        Decimal('116') * Decimal('0.9') / Decimal('1.16'))


def test_the_amount_to_invoice_at_a_date(company):
    line = _line(company, price='10')
    line.write({'qty_received': Decimal('5')})
    _bill(company, line, '2')
    line.flush_recordset()
    line.invalidate_recordset()
    assert line.amount_to_invoice_at_date == Decimal('30')


def _set_order_state(line, state):
    order_model = type(line.order_id)
    order_model.objects.filter(pk=line.order_id.id).update(state=state)
    line.order_id.invalidate_recordset()
    line.invalidate_recordset()


def test_a_receipt_or_an_entry_does_not_count(company):
    """Sólo ``in_invoice`` suma y ``in_refund`` resta (``odoo19c:
    :195-199``); cualquier otro tipo de asiento se ignora."""
    line = _line(company)
    _bill(company, line, '3', move_type='in_receipt')
    _bill(company, line, '4', move_type='entry')
    assert line._prepare_qty_invoiced()[line] == 0


def test_a_line_without_bills_has_nothing_invoiced(company):
    line = _line(company)
    assert line._prepare_qty_invoiced()[line] == 0
    line.flush_recordset()
    line.invalidate_recordset()
    assert line.qty_invoiced == 0


def test_only_a_purchase_order_has_something_to_invoice(company):
    """``qty_to_invoice`` sólo es distinto de cero con
    ``order_id.state == 'purchase'`` (``odoo19c: :171``): también ``done``
    y ``cancel`` dan cero."""
    line = _line(company)
    line.order_id.button_confirm()
    line.flush_recordset()
    line.invalidate_recordset()
    assert line.qty_to_invoice == Decimal('10')
    for state in ('done', 'cancel'):
        _set_order_state(line, state)
        line._compute_qty_invoiced()
        assert line.qty_to_invoice == 0, state


def test_an_over_billed_line_has_a_negative_quantity_to_invoice(company):
    line = _line(company, qty='2')
    line.order_id.button_confirm()
    _bill(company, line, '5')
    line.flush_recordset()
    line.invalidate_recordset()
    assert line.qty_to_invoice == Decimal('-3')


def test_today_is_not_in_the_past_and_undated_bills_are_left_out(company):
    """``_date_in_the_past`` compara con ``<`` estricto (``odoo19c:
    :708-712``) y ``_get_invoice_lines`` descarta las facturas sin
    ``invoice_date`` (``:205-207``)."""
    line = _line(company)
    today = timezone.localdate()
    _bill(company, line, '2', invoice_date=today - datetime.timedelta(days=5))
    _bill(company, line, '3')
    line.flush_recordset()
    line.invalidate_recordset()
    with context_scope(accrual_entry_date=today.isoformat()):
        assert line.qty_invoiced_at_date == Decimal('5')
    past = (today - datetime.timedelta(days=1)).isoformat()
    with context_scope(accrual_entry_date=past):
        assert line.qty_invoiced_at_date == Decimal('2')


def test_get_invoice_lines_wants_one_line(company):
    first, second = _line(company), _line(company)
    with pytest.raises(ValueError):
        (first | second)._get_invoice_lines()


def test_the_invoiced_quantity_follows_its_bills(company):
    """El ``depends`` recorre ``invoice_lines.move_id.state`` y
    ``invoice_lines.quantity`` (``odoo19c: :164``)."""
    line = _line(company)
    move = _bill(company, line, '3')
    line.flush_recordset()
    line.invalidate_recordset()
    assert line.qty_invoiced == Decimal('3')
    [bill_line] = AccountMoveLine.objects.filter(move=move)
    bill_line.quantity = Decimal('4')
    bill_line.save()
    line.invalidate_recordset()
    assert line.qty_invoiced == Decimal('4')
    move.state = 'cancel'
    move.save()
    line.invalidate_recordset()
    assert line.qty_invoiced == 0
