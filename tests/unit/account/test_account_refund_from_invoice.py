"""RED→GREEN — nota de crédito ``out_refund`` como reversión de una factura.

Rebanada 2 de H-API-08 (par simétrico de la rebanada 1): un servicio crea un
``account.move`` ``out_refund`` que **revierte** una factura ``out_invoice``
publicada — cada apunte con débito/crédito intercambiados sobre la misma cuenta,
de modo que el asiento queda balanceado por construcción. Análogo a Odoo
``account.move._reverse_moves`` (nota de crédito de cliente).

Independiente de #185 (toma la factura, que ya tiene su ``company``) y de la
deriva ``payment``/``payments`` (esta bloquea el *wiring* al flujo de reembolso,
no la mecánica de reversión).
"""
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from exceptions import UserError
from addons.account.models import AccountAccount, AccountJournal, AccountMove
from addons.account.services import (
    create_invoice_from_sale_order,
    create_refund_from_invoice,
)
from addons.catalogue.models import Category, Product
from addons.platform.models import Company
from addons.sale.models import SaleOrder


@pytest.fixture
def company(db):
    return Company.objects.create(code='acme', name='ACME')


@pytest.fixture
def chart(db, company):
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
def posted_invoice(db, company, chart):
    cat = Category.objects.create(name='Cat', slug='cat-ref', is_active=True)
    product = Product.objects.create(
        name='Prod', slug='prod-ref', sku='REF-001', description='',
        price=Decimal('116.00'), stock=5, is_active=True, is_published=True)
    product.categories.add(cat)
    order = SaleOrder.objects.create(
        state=SaleOrder.STATE_SALE, cart_token=uuid.uuid4())
    order.order_line.create(
        product=product, name='Prod', price_unit=Decimal('116.00'),
        product_uom_qty=1)
    invoice = create_invoice_from_sale_order(order, company)
    invoice.post()
    invoice.refresh_from_db()
    return invoice


@pytest.mark.django_db
class TestCreateRefundFromInvoice:
    def test_creates_balanced_out_refund(self, posted_invoice):
        refund = create_refund_from_invoice(posted_invoice)

        assert refund.move_type == 'out_refund'
        assert refund.company_id == posted_invoice.company_id
        assert refund.partner_id == posted_invoice.partner_id
        assert refund.is_balanced() is True

        refund.post()
        refund.refresh_from_db()
        assert refund.state == 'posted'
        assert refund.amount_total == posted_invoice.amount_total

    def test_lines_reverse_debit_and_credit_by_account(self, posted_invoice):
        refund = create_refund_from_invoice(posted_invoice)

        inv_by_acct = {
            line.account_id: (line.debit, line.credit)
            for line in posted_invoice.line_ids.all()
        }
        ref_by_acct = {
            line.account_id: (line.debit, line.credit)
            for line in refund.line_ids.all()
        }
        assert set(ref_by_acct) == set(inv_by_acct)
        for account_id, (inv_debit, inv_credit) in inv_by_acct.items():
            ref_debit, ref_credit = ref_by_acct[account_id]
            assert ref_debit == inv_credit
            assert ref_credit == inv_debit

    def test_refuses_non_invoice_move(self, company, chart):
        entry = AccountMove.objects.create(
            move_type='entry', company=company, journal=chart['journal'],
            date=timezone.now().date())
        with pytest.raises(UserError):
            create_refund_from_invoice(entry)

    def test_refuses_draft_invoice(self, db, company, chart):
        draft = AccountMove.objects.create(
            move_type='out_invoice', company=company, journal=chart['journal'],
            date=timezone.now().date())
        with pytest.raises(UserError):
            create_refund_from_invoice(draft)
