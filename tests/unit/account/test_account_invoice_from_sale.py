"""RED→GREEN — cablear el eje factura ``account.move`` desde una ``SaleOrder``.

Rebanada 1 de H-API-08 (``account.move`` modelado pero 0 instanciaciones desde
el flujo O2C — PROVEN: ``grep -rn "AccountMove(" src/addons`` da 1, la del propio
modelo). Un servicio crea un ``account.move`` (``out_invoice``) balanceado desde
una ``SaleOrder`` confirmada, respetando la doble entrada que ``AccountMove.post``
exige (``_check_balanced``: debe == haber). Análogo a Odoo
``sale.order._create_invoices()``.

Fuera de esta rebanada (no "parcial justificado" — sub-rebanadas explícitas):
auto-trigger en ``action_confirm`` (etapa 4a/5), resolución de ``company`` desde
``SaleOrder`` (acoplado a #185 SOL-085 S3, que añade la FK ``company``), y
``out_refund`` (acoplado a la deriva de addon ``payment``/``payments``).
"""
import uuid
from decimal import Decimal

import pytest

from exceptions import UserError
from addons.account.models import AccountAccount, AccountJournal
from addons.account.services import create_invoice_from_sale_order
from tests.factories.product_factory import make_category, make_product
from addons.platform.models import Company
from addons.sale.models import SaleOrder


@pytest.fixture
def company(db):
    return Company.objects.create(code='acme', name='ACME')


@pytest.fixture
def chart(db, company):
    """Diario de ventas + cuentas mínimas por ``company`` (plan de cuentas)."""
    return {
        'journal': AccountJournal.objects.create(
            name='Ventas', code='VEN', type='sale', company=company),
        'receivable': AccountAccount.objects.create(
            code='105', name='Clientes', account_type='asset_receivable',
            company=company),
        'income': AccountAccount.objects.create(
            code='401', name='Ventas', account_type='income', company=company),
        'tax': AccountAccount.objects.create(
            code='208', name='IVA trasladado',
            account_type='liability_current', company=company),
    }


@pytest.fixture
def confirmed_order(db):
    """``SaleOrder`` confirmada (``state='sale'``) con una línea (total 116.00)."""
    cat = make_category('Cat')
    product = make_product(
        name='Prod', default_code='INV-001', price=Decimal('116.00'),
        stock=5, categ=cat)
    order = SaleOrder.objects.create(
        state=SaleOrder.STATE_SALE, cart_token=uuid.uuid4())
    order.order_line.create(
        product=product, name='Prod', price_unit=Decimal('116.00'),
        product_uom_qty=1)
    return order


@pytest.mark.django_db
class TestCreateInvoiceFromSaleOrder:
    def test_creates_balanced_out_invoice(self, company, chart, confirmed_order):
        move = create_invoice_from_sale_order(confirmed_order, company)

        assert move.move_type == 'out_invoice'
        assert move.company_id == company.pk
        assert move.partner_id == confirmed_order.partner_id
        assert move.is_balanced() is True

        move.post()
        move.refresh_from_db()
        assert move.state == 'posted'
        assert move.amount_total == confirmed_order.amount_total

    def test_double_entry_matches_order_total(self, company, chart,
                                              confirmed_order):
        move = create_invoice_from_sale_order(confirmed_order, company)
        total = confirmed_order.amount_total

        debit = sum((line.debit for line in move.line_ids.all()),
                    Decimal('0.00'))
        credit = sum((line.credit for line in move.line_ids.all()),
                     Decimal('0.00'))
        assert debit == total
        assert credit == total

    def test_income_and_tax_split_by_account(self, company, chart,
                                             confirmed_order):
        move = create_invoice_from_sale_order(confirmed_order, company)

        income_credit = sum(
            (line.credit for line in move.line_ids.all()
             if line.account_id == chart['income'].pk), Decimal('0.00'))
        tax_credit = sum(
            (line.credit for line in move.line_ids.all()
             if line.account_id == chart['tax'].pk), Decimal('0.00'))
        assert income_credit == confirmed_order.amount_untaxed
        assert tax_credit == confirmed_order.amount_tax

    def test_refuses_order_without_lines(self, company, chart, db):
        empty = SaleOrder.objects.create(
            state=SaleOrder.STATE_SALE, cart_token=uuid.uuid4())
        with pytest.raises(UserError):
            create_invoice_from_sale_order(empty, company)

    def test_refuses_when_no_sale_journal(self, company, confirmed_order, db):
        with pytest.raises(UserError):
            create_invoice_from_sale_order(confirmed_order, company)
