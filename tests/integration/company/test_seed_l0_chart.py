"""RED→GREEN — ``seed_l0_chart``: carta contable L0 de Kaupamex (H-API-05).

El cobro de suscripción (``SubscriptionInvoice.post_to_ledger``) asienta un
``account.move`` en los libros de la system company (Kaupamex, el operador L0).
Sin diario de ventas + cuentas por-cobrar/ingreso, ``post_to_ledger`` falla-fuerte
(``UserError``). Este comando siembra ese mínimo, **idempotente**, para que el
eje contable L0 funcione en un entorno real (no sólo bajo el fixture de test).

Vive en ``company`` (dueño del concepto L0/system) y **lee** los modelos de
``account`` — dirección de dependencia permitida (``company`` → ``account``);
nunca al revés (DEC-FW-01). Ver :ref:`diseno-motor-facturacion-recurrente-l0`.
"""
from decimal import Decimal
from io import StringIO

import pytest

from django.core.management import call_command

from addons.account.models import AccountAccount, AccountJournal
from addons.authz.models import Module
from addons.company.models import (
    Company,
    CompanyModuleSubscription,
    SubscriptionBillingRun,
    SubscriptionInvoice,
)

pytestmark = pytest.mark.django_db


class TestSeedL0Chart:
    def test_creates_sales_journal_for_system_company(self):
        call_command('seed_l0_chart', stdout=StringIO())
        system = Company.get_system()
        journal = AccountJournal.objects.get(company=system, type='sale')
        assert journal.active is True

    def test_creates_receivable_and_income_accounts(self):
        call_command('seed_l0_chart', stdout=StringIO())
        system = Company.get_system()
        assert AccountAccount.objects.filter(
            company=system, account_type='asset_receivable',
            deprecated=False).exists()
        assert AccountAccount.objects.filter(
            company=system, account_type='income',
            deprecated=False).exists()

    def test_is_idempotent(self):
        call_command('seed_l0_chart', stdout=StringIO())
        call_command('seed_l0_chart', stdout=StringIO())
        system = Company.get_system()
        assert AccountJournal.objects.filter(
            company=system, type='sale').count() == 1
        assert AccountAccount.objects.filter(
            company=system, account_type='asset_receivable').count() == 1
        assert AccountAccount.objects.filter(
            company=system, account_type='income').count() == 1

    def test_unblocks_post_to_ledger(self):
        # Sin el fixture ``l0_chart``: el seed debe bastar para asentar el
        # cobro L0 end-to-end.
        call_command('seed_l0_chart', stdout=StringIO())
        tenant = Company.objects.create(code='acme', name='Acme')
        module = Module.objects.create(code='catalogue', name='catalogue')
        sub = CompanyModuleSubscription.objects.create(
            company=tenant, module=module,
            status=CompanyModuleSubscription.Status.ACTIVE,
            billing_cycle='monthly', price=Decimal('199.00'))
        run = SubscriptionBillingRun.objects.create(period='2026-08')
        invoice = SubscriptionInvoice.objects.create(
            company=tenant, subscription=sub, run=run, period='2026-08',
            amount=Decimal('199.00'), currency='MXN')

        move = invoice.post_to_ledger()

        assert move.state == 'posted'
        assert move.company_id == Company.get_system().pk
        assert move.amount_total == invoice.amount
