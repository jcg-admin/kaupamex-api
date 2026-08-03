"""Billing pago-por-módulo L0 — estructura de precios (SOL-085 S4 / #180).

``ModulePrice`` es el catálogo de tarifas por módulo × ciclo, con vigencia
(``effective_from``/``effective_to``) para versionar tarifas sin mutar el
histórico. Al suscribir, el precio vigente se **copia** a
``CompanyModuleSubscription`` (``price`` + ``billing_cycle``) — inmutabilidad
histórica: un cambio de tarifa posterior NO reescribe lo que una company ya
paga (mismo principio que los snapshots de precio de órdenes).

Estos tests fijan la ESTRUCTURA (DEC-T6). Los montos son **datos** que el
operador siembra — no se inventan aquí; se usan valores de prueba arbitrarios.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

import pytest

from addons.authz.models import Module
from addons.platform.models import (
    Company,
    CompanyModuleSubscription,
    ModulePrice,
)

pytestmark = pytest.mark.django_db


def _module(code='catalogue'):
    return Module.objects.create(code=code, name=code)


def test_current_returns_active_price_in_window():
    m = _module()
    now = timezone.now()
    price = ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
        price=Decimal('199.00'), effective_from=now - timedelta(days=1),
    )
    got = ModulePrice.current(m, ModulePrice.BillingCycle.MONTHLY)
    assert got == price


def test_current_returns_none_when_no_price():
    m = _module()
    assert ModulePrice.current(m, ModulePrice.BillingCycle.MONTHLY) is None


def test_current_ignores_expired_and_future_rows():
    m = _module()
    now = timezone.now()
    # Expirada.
    ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
        price=Decimal('99.00'), effective_from=now - timedelta(days=30),
        effective_to=now - timedelta(days=1),
    )
    # Futura.
    ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
        price=Decimal('299.00'), effective_from=now + timedelta(days=1),
    )
    assert ModulePrice.current(m, ModulePrice.BillingCycle.MONTHLY) is None


def test_current_picks_latest_effective_from_on_rate_change():
    m = _module()
    now = timezone.now()
    ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.ANNUAL,
        price=Decimal('1990.00'), effective_from=now - timedelta(days=100),
    )
    newer = ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.ANNUAL,
        price=Decimal('2490.00'), effective_from=now - timedelta(days=1),
    )
    assert ModulePrice.current(m, ModulePrice.BillingCycle.ANNUAL) == newer


def test_current_is_scoped_by_billing_cycle():
    m = _module()
    now = timezone.now()
    ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
        price=Decimal('199.00'), effective_from=now - timedelta(days=1),
    )
    assert ModulePrice.current(m, ModulePrice.BillingCycle.ANNUAL) is None


def test_apply_current_price_copies_price_and_keeps_cycle():
    company = Company.objects.create(code='c1', name='C1')
    m = _module()
    now = timezone.now()
    ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
        price=Decimal('199.00'), effective_from=now - timedelta(days=1),
    )
    sub = CompanyModuleSubscription(
        company=company, module=m,
        status=CompanyModuleSubscription.Status.TRIAL,
        billing_cycle=ModulePrice.BillingCycle.MONTHLY,
    )
    sub.apply_current_price()
    assert sub.price == Decimal('199.00')
    assert sub.billing_cycle == ModulePrice.BillingCycle.MONTHLY


def test_copied_price_is_immutable_after_rate_change():
    company = Company.objects.create(code='c2', name='C2')
    m = _module()
    now = timezone.now()
    old = ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
        price=Decimal('199.00'), effective_from=now - timedelta(days=10),
    )
    sub = CompanyModuleSubscription(
        company=company, module=m,
        status=CompanyModuleSubscription.Status.TRIAL,
        billing_cycle=ModulePrice.BillingCycle.MONTHLY,
    )
    sub.apply_current_price()
    sub.save()
    # Cambio de tarifa: cerrar la vieja, abrir una nueva más cara.
    old.effective_to = now
    old.save(update_fields=['effective_to', 'updated_at'])
    ModulePrice.objects.create(
        module=m, billing_cycle=ModulePrice.BillingCycle.MONTHLY,
        price=Decimal('249.00'), effective_from=now,
    )
    sub.refresh_from_db()
    assert sub.price == Decimal('199.00')  # no se reescribe retroactivamente


def test_apply_current_price_without_row_leaves_price_none():
    company = Company.objects.create(code='c3', name='C3')
    m = _module()
    sub = CompanyModuleSubscription(
        company=company, module=m,
        status=CompanyModuleSubscription.Status.TRIAL,
        billing_cycle=ModulePrice.BillingCycle.MONTHLY,
    )
    sub.apply_current_price()
    assert sub.price is None  # módulo sin tarifa (free/no sembrado)
