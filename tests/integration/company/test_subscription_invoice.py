"""Persistencia del motor de facturación recurrente L0 (UC-PLT-18 / #180).

Capa de persistencia que el ``company/billing.py`` sin estado no tenía
(H-API-01/H-API-02): ``SubscriptionBillingRun`` (resumen de la corrida) y
``SubscriptionInvoice`` (documento de cobro por período, con **idempotencia**
``unique_together (subscription, period)`` y **precio congelado**).

Diseño: :ref:`diseno-motor-facturacion-recurrente-l0`. Los montos son datos de
prueba arbitrarios (no se inventan precios de negocio).
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError

from addons.authz.models import Module
from addons.company.models import (
    Company,
    CompanyModuleSubscription,
    SubscriptionBillingRun,
    SubscriptionInvoice,
)

pytestmark = pytest.mark.django_db


def _active_sub(company, code, price):
    m = Module.objects.create(code=code, name=code)
    sub = CompanyModuleSubscription(
        company=company, module=m,
        status=CompanyModuleSubscription.Status.ACTIVE,
        billing_cycle='monthly', price=Decimal(price),
    )
    sub.save()
    return sub


def test_billing_run_defaults_counters_to_zero():
    run = SubscriptionBillingRun.objects.create(
        period='2026-08',
        triggered_by=SubscriptionBillingRun.TriggeredBy.OPERATOR,
    )
    assert run.invoices_issued == 0
    assert run.amount_charged == Decimal('0.00')
    assert run.failures == 0
    assert run.finished_at is None


def test_invoice_freezes_amount_and_defaults_to_draft():
    c = Company.objects.create(code='acme', name='Acme')
    sub = _active_sub(c, 'catalogue', '199.00')
    run = SubscriptionBillingRun.objects.create(period='2026-08')
    inv = SubscriptionInvoice.objects.create(
        company=c, subscription=sub, run=run, period='2026-08',
        amount=sub.price, currency='MXN',
    )
    assert inv.status == SubscriptionInvoice.Status.DRAFT
    assert inv.amount == Decimal('199.00')
    assert inv.issued_at is None and inv.paid_at is None


def test_invoice_idempotent_per_subscription_and_period():
    c = Company.objects.create(code='acme', name='Acme')
    sub = _active_sub(c, 'catalogue', '199.00')
    run = SubscriptionBillingRun.objects.create(period='2026-08')
    SubscriptionInvoice.objects.create(
        company=c, subscription=sub, run=run, period='2026-08',
        amount=sub.price,
    )
    # Reintentar la corrida por el mismo periodo NO debe duplicar la factura.
    with pytest.raises(IntegrityError):
        SubscriptionInvoice.objects.create(
            company=c, subscription=sub, run=run, period='2026-08',
            amount=sub.price,
        )


def test_invoice_same_subscription_different_period_is_allowed():
    c = Company.objects.create(code='acme', name='Acme')
    sub = _active_sub(c, 'catalogue', '199.00')
    run1 = SubscriptionBillingRun.objects.create(period='2026-08')
    run2 = SubscriptionBillingRun.objects.create(period='2026-09')
    SubscriptionInvoice.objects.create(
        company=c, subscription=sub, run=run1, period='2026-08', amount=sub.price,
    )
    SubscriptionInvoice.objects.create(
        company=c, subscription=sub, run=run2, period='2026-09', amount=sub.price,
    )
    assert SubscriptionInvoice.objects.filter(subscription=sub).count() == 2


def test_invoice_status_lifecycle_values():
    values = set(SubscriptionInvoice.Status.values)
    assert values == {'draft', 'issued', 'paid', 'failed', 'void'}


def test_run_reverse_relation_to_invoices():
    c = Company.objects.create(code='acme', name='Acme')
    sub = _active_sub(c, 'catalogue', '199.00')
    run = SubscriptionBillingRun.objects.create(period='2026-08')
    inv = SubscriptionInvoice.objects.create(
        company=c, subscription=sub, run=run, period='2026-08', amount=sub.price,
    )
    assert list(run.invoices.all()) == [inv]
    assert list(sub.invoices.all()) == [inv]
    assert list(c.subscription_invoices.all()) == [inv]
