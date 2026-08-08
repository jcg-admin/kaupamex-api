"""RED→GREEN — ``SubscriptionInvoice.post_to_ledger()`` (H-API-05).

El eje contable del cobro L0: la ``SubscriptionInvoice`` (company→Kaupamex) se
asienta como un ``account.move`` de doble entrada en los **libros de Kaupamex**
(la system company, el operador L0), NO en los del tenant. Kaupamex vende el
acceso a los módulos → ``out_invoice``: por cobrar (débito) contra ingreso de
plataforma (crédito). Puente **explícito e idempotente** por una FK
``account_move`` (mismo patrón que el O2C, H-API-08 (a)); NO se auto-dispara en
la corrida (rompería flujos sin chart L0). Ver
:ref:`diseno-motor-facturacion-recurrente-l0`.
"""
from decimal import Decimal

import pytest

from exceptions import UserError
from addons.account.models import AccountAccount, AccountJournal, AccountMove
from addons.authz.models import Module
from addons.sale_subscription.models import (
    CompanyModuleSubscription,
    SubscriptionBillingRun,
    SubscriptionInvoice,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


@pytest.fixture
def tenant():
    return ResCompany.objects.create(code='acme', name='Acme')


@pytest.fixture
def l0_chart():
    """System company (Kaupamex) con su plan de cuentas L0 mínimo."""
    system = ResCompany.get_system()
    AccountJournal.objects.create(
        name='Ventas plataforma', code='VEN', type='sale', company=system)
    AccountAccount.objects.create(
        code='105', name='Clientes L0', account_type='asset_receivable',
        company=system)
    AccountAccount.objects.create(
        code='401', name='Ingreso plataforma', account_type='income',
        company=system)
    return system


@pytest.fixture
def invoice(tenant):
    module = Module.objects.create(code='catalogue', name='catalogue')
    sub = CompanyModuleSubscription.objects.create(
        company=tenant, module=module,
        status=CompanyModuleSubscription.Status.ACTIVE,
        billing_cycle='monthly', price=Decimal('199.00'))
    run = SubscriptionBillingRun.objects.create(period='2026-08')
    return SubscriptionInvoice.objects.create(
        company=tenant, subscription=sub, run=run, period='2026-08',
        amount=Decimal('199.00'), currency='MXN')


class TestSubscriptionPostToLedger:
    def test_creates_posted_out_invoice(self, l0_chart, invoice):
        move = invoice.post_to_ledger()
        assert move.move_type == 'out_invoice'
        assert move.state == 'posted'
        assert move.amount_total == invoice.amount

    def test_booked_in_system_company(self, l0_chart, invoice):
        move = invoice.post_to_ledger()
        # Los libros son de Kaupamex (L0), NO del tenant.
        assert move.company_id == l0_chart.pk
        assert move.company_id != invoice.company_id

    def test_links_invoice_to_move(self, l0_chart, invoice):
        move = invoice.post_to_ledger()
        invoice.refresh_from_db()
        assert invoice.account_move_id == move.pk

    def test_is_idempotent(self, l0_chart, invoice):
        first = invoice.post_to_ledger()
        second = invoice.post_to_ledger()
        assert second.pk == first.pk
        assert AccountMove.objects.count() == 1

    def test_double_entry_receivable_vs_income(self, l0_chart, invoice):
        move = invoice.post_to_ledger()
        debit = sum((l.debit for l in move.line_ids.all()), Decimal('0.00'))
        credit = sum((l.credit for l in move.line_ids.all()), Decimal('0.00'))
        assert debit == invoice.amount
        assert credit == invoice.amount

    def test_requires_l0_chart(self, invoice):
        # Sin diario/cuentas de la system company → falla ruidoso (fail-loud).
        ResCompany.get_system()  # existe, pero sin chart
        with pytest.raises(UserError):
            invoice.post_to_ledger()
