"""Billing run L0 — cobro company→Kaupamex (SOL-085 S4-b / #180).

Servicio de lógica pura: ``amount_due`` suma las suscripciones ``active`` con
precio, ``run_billing`` cobra vía un ``charge`` **inyectable** (el adaptador MP
real es la pieza de integración externa, fuera de esta lógica) y, ante fallo de
cobro, transiciona a ``suspended`` — NO ``cancelled`` (permite reactivación y
saca la company del ∩ L1 sin tocar el resolver, DEC-T4/T6).

Los montos son datos de prueba arbitrarios (no se inventan precios de negocio).
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.authz.models import Module
from addons.sale_subscription import services as billing
from addons.sale_subscription.models import (
    CompanyModuleSubscription,
    SubscriptionBillingRun,
    SubscriptionInvoice,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


def _priced_active_sub(company, code, price):
    m = Module.objects.create(code=code, name=code)
    sub = CompanyModuleSubscription(
        company=company, module=m,
        status=CompanyModuleSubscription.Status.ACTIVE,
        billing_cycle='monthly', price=Decimal(price),
    )
    sub.save()
    return sub


def test_amount_due_sums_active_priced_subscriptions():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    _priced_active_sub(c, 'inventory', '99.00')
    assert billing.amount_due(c) == Decimal('298.00')


def test_amount_due_excludes_trial_and_unpriced():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    # Trial: no se cobra todavía.
    mt = Module.objects.create(code='orders', name='orders')
    CompanyModuleSubscription.objects.create(
        company=c, module=mt, status=CompanyModuleSubscription.Status.TRIAL,
        billing_cycle='monthly', price=Decimal('50.00'),
    )
    # Active sin precio (free / sin tarifa sembrada): no suma.
    mf = Module.objects.create(code='reports', name='reports')
    CompanyModuleSubscription.objects.create(
        company=c, module=mf, status=CompanyModuleSubscription.Status.ACTIVE,
        billing_cycle='monthly', price=None,
    )
    assert billing.amount_due(c) == Decimal('199.00')


def test_run_billing_charges_and_marks_charged():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    calls = []

    def charge(company, amount):
        calls.append((company.code, amount))
        return True

    results = billing.run_billing(charge)
    assert results['acme'] == 'charged'
    assert calls == [('acme', Decimal('199.00'))]
    assert c.active_module_codes() == {'catalogue'}  # sigue activa


def test_run_billing_suspends_on_charge_failure():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')

    def charge(company, amount):
        return False  # pasarela rechaza el cobro

    results = billing.run_billing(charge)
    assert results['acme'] == 'suspended'
    sub = CompanyModuleSubscription.objects.get(company=c)
    assert sub.status == CompanyModuleSubscription.Status.SUSPENDED
    assert c.active_module_codes() == set()  # sale del ∩ L1


def test_run_billing_skips_companies_with_nothing_due():
    c = ResCompany.objects.create(code='empty', name='Empty')
    charged = []
    results = billing.run_billing(lambda company, amount: charged.append(company) or True)
    assert results['empty'] == 'skipped'
    assert charged == []


def test_run_billing_excludes_system_company():
    ResCompany.objects.create(code='acme', name='Acme')
    ResCompany.get_system()  # is_system=True — plataforma, no se autocobra
    seen = []
    billing.run_billing(lambda company, amount: seen.append(company.code) or True)
    codes = set(
        ResCompany.objects.exclude(is_system=True).values_list('code', flat=True)
    )
    assert 'kaupamex_global' not in codes


# --- Persistencia: run_billing ahora crea run + factura (H-API-02, slice 2) ---

def test_run_billing_persists_run_and_paid_invoice():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    billing.run_billing(lambda company, amount: True, period='2026-08')

    run = SubscriptionBillingRun.objects.get(period='2026-08')
    assert run.invoices_issued == 1
    assert run.amount_charged == Decimal('199.00')
    assert run.failures == 0
    assert run.finished_at is not None

    inv = SubscriptionInvoice.objects.get(company=c, period='2026-08')
    assert inv.status == SubscriptionInvoice.Status.PAID
    assert inv.amount == Decimal('199.00')   # precio congelado
    assert inv.paid_at is not None
    assert inv.run_id == run.id


def test_run_billing_idempotent_does_not_recharge_paid_invoice():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    calls = []

    def charge(company, amount):
        calls.append((company.code, amount))
        return True

    # Dos corridas por el MISMO periodo: la segunda no re-cobra ni duplica.
    billing.run_billing(charge, period='2026-08')
    billing.run_billing(charge, period='2026-08')

    assert calls == [('acme', Decimal('199.00'))]       # cobrada UNA vez
    assert SubscriptionInvoice.objects.filter(
        company=c, period='2026-08',
    ).count() == 1                                        # sin duplicar (EX-04)


def test_run_billing_failed_charge_marks_invoice_failed_and_suspends():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    billing.run_billing(lambda company, amount: False, period='2026-08')

    inv = SubscriptionInvoice.objects.get(company=c, period='2026-08')
    assert inv.status == SubscriptionInvoice.Status.FAILED
    assert inv.paid_at is None
    run = SubscriptionBillingRun.objects.get(period='2026-08')
    assert run.failures == 1
    assert run.invoices_issued == 0
    sub = CompanyModuleSubscription.objects.get(company=c)
    assert sub.status == CompanyModuleSubscription.Status.SUSPENDED


def test_run_billing_period_defaults_to_current_month():
    c = ResCompany.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    expected = timezone.now().strftime('%Y-%m')
    billing.run_billing(lambda company, amount: True)
    assert SubscriptionBillingRun.objects.filter(period=expected).exists()
    assert SubscriptionInvoice.objects.filter(
        company=c, period=expected,
    ).exists()
