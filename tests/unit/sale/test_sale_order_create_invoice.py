"""RED→GREEN — ``SaleOrder.action_create_invoice()`` (H-API-08 sub-rebanada (a)).

``sale`` es dueño del puente O2C→factura (dirección de dependencia correcta
``sale``→``account``; ``account`` queda limpio, *duck-typing* la orden). El
puente es **idempotente** vía una FK ``sale``→``account`` ``invoice``: una orden
ya facturada devuelve su factura existente en vez de emitir un duplicado —
espeja Odoo ``sale.order._create_invoices`` saltando órdenes ya facturadas.
Postea el asiento al crearlo.

**NO** se dispara automático en ``action_confirm``: auto-facturar al confirmar
es una política *config-gated* (Odoo ``website_sale.automatic_invoice``) que
rompería los flujos de confirmación sin plan de cuentas — se difiere como
decisión de producto aparte (sub-rebanada de política).
"""
import uuid
from decimal import Decimal

import pytest

from exceptions import UserError
from addons.account.models import AccountAccount, AccountJournal, AccountMove
from addons.company.models import Company
from addons.sale.models import SaleOrder
from tests.factories.product_factory import make_category, make_product


@pytest.fixture
def company(db):
    return Company.objects.create(code='acme', name='ACME')


@pytest.fixture
def chart(db, company):
    """Diario de ventas + cuentas mínimas por ``company``."""
    AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)
    AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    AccountAccount.objects.create(
        code='208', name='IVA trasladado', account_type='liability_current',
        company=company)


@pytest.fixture
def confirmed_order(db, company):
    """``SaleOrder`` confirmada de ``company`` con una línea (total 116.00)."""
    cat = make_category(name='Cat')
    product = make_product(name='Prod', price=Decimal('116.00'), stock=5, categ=cat)
    order = SaleOrder.objects.create(
        state=SaleOrder.STATE_SALE, company=company, cart_token=uuid.uuid4())
    order.order_line.create(
        product=product, name='Prod', price_unit=Decimal('116.00'),
        product_uom_qty=1)
    return order


@pytest.mark.django_db
class TestSaleOrderCreateInvoice:
    def test_creates_and_posts_invoice(self, chart, confirmed_order):
        move = confirmed_order.action_create_invoice()
        assert move.move_type == 'out_invoice'
        assert move.state == 'posted'
        assert move.amount_total == confirmed_order.amount_total

    def test_links_order_to_invoice(self, chart, confirmed_order):
        move = confirmed_order.action_create_invoice()
        confirmed_order.refresh_from_db()
        assert confirmed_order.invoice_id == move.pk
        assert move.company_id == confirmed_order.company_id

    def test_is_idempotent(self, chart, confirmed_order):
        first = confirmed_order.action_create_invoice()
        second = confirmed_order.action_create_invoice()
        assert second.pk == first.pk
        assert AccountMove.objects.count() == 1

    def test_requires_company(self, chart, db):
        cat = make_category(name='C')
        product = make_product(name='P', price=Decimal('50.00'), stock=1, categ=cat)
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_SALE, cart_token=uuid.uuid4())  # sin company
        order.order_line.create(
            product=product, name='P', price_unit=Decimal('50.00'),
            product_uom_qty=1)
        with pytest.raises(UserError):
            order.action_create_invoice()

    def test_requires_confirmed_state(self, chart, company, db):
        draft = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, company=company, cart_token=uuid.uuid4())
        with pytest.raises(UserError):
            draft.action_create_invoice()
