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

from addons.authz.models import Module
from addons.company import billing
from addons.company.models import Company, CompanyModuleSubscription

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
    c = Company.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')
    _priced_active_sub(c, 'inventory', '99.00')
    assert billing.amount_due(c) == Decimal('298.00')


def test_amount_due_excludes_trial_and_unpriced():
    c = Company.objects.create(code='acme', name='Acme')
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
    c = Company.objects.create(code='acme', name='Acme')
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
    c = Company.objects.create(code='acme', name='Acme')
    _priced_active_sub(c, 'catalogue', '199.00')

    def charge(company, amount):
        return False  # pasarela rechaza el cobro

    results = billing.run_billing(charge)
    assert results['acme'] == 'suspended'
    sub = CompanyModuleSubscription.objects.get(company=c)
    assert sub.status == CompanyModuleSubscription.Status.SUSPENDED
    assert c.active_module_codes() == set()  # sale del ∩ L1


def test_run_billing_skips_companies_with_nothing_due():
    c = Company.objects.create(code='empty', name='Empty')
    charged = []
    results = billing.run_billing(lambda company, amount: charged.append(company) or True)
    assert results['empty'] == 'skipped'
    assert charged == []


def test_run_billing_excludes_system_company():
    Company.objects.create(code='acme', name='Acme')
    Company.get_system()  # is_system=True — plataforma, no se autocobra
    seen = []
    billing.run_billing(lambda company, amount: seen.append(company.code) or True)
    codes = set(
        Company.objects.exclude(is_system=True).values_list('code', flat=True)
    )
    assert 'kaupamex_global' not in codes
