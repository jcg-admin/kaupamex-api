"""Contract for the Tenant/L1 foundation (plataforma-kaupamex, capa L1).

Design: ``docs/source/gestion/pm/api/iniciativas/plataforma-kaupamex/
analisis-modelo-tenant-l1-foundation.rst`` — ``Tenant`` (L1 root) +
``TenantModuleSubscription`` (per-module billing/gating) reusing the existing
``authz.Module`` pivot (L1<->L2). Slice 1: models + the L1-a "active module
codes" primitive **in isolation** — NOT yet wired into ``authz.services.
resolve_capabilities`` (that needs a user<->tenant link, a later slice), so the
existing suite stays green.

TDD for the Kaupamex platform base loop (design-first -> construction).
"""
import datetime

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.authz.models import Module
from apps.tenancy.models import Tenant, TenantModuleSubscription

pytestmark = pytest.mark.django_db


class TestTenantModel:
    def test_create_and_str(self):
        t = Tenant.objects.create(code="practicayoruba", name="PracticaYoruba")
        assert str(t) == "practicayoruba"
        # default status is TRIAL (a tenant is born on trial until activated)
        assert t.status == Tenant.Status.TRIAL

    def test_code_is_unique(self):
        Tenant.objects.create(code="acme", name="Acme")
        with pytest.raises(IntegrityError):
            Tenant.objects.create(code="acme", name="Acme 2")


class TestTenantModuleSubscription:
    def test_unique_per_tenant_module(self):
        t = Tenant.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="catalogue", name="Catálogo")
        TenantModuleSubscription.objects.create(tenant=t, module=m)
        with pytest.raises(IntegrityError):
            TenantModuleSubscription.objects.create(tenant=t, module=m)

    def test_is_active_respects_status_and_expiry(self):
        t = Tenant.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="orders", name="Órdenes")
        now = timezone.now()
        active = TenantModuleSubscription.objects.create(
            tenant=t, module=m,
            status=TenantModuleSubscription.Status.ACTIVE,
            expires_at=now + datetime.timedelta(days=30),
        )
        assert active.is_active(now) is True

        active.expires_at = now - datetime.timedelta(days=1)
        assert active.is_active(now) is False  # expired

        active.expires_at = None
        active.status = TenantModuleSubscription.Status.SUSPENDED
        assert active.is_active(now) is False  # suspended never active

    def test_no_expiry_means_active_forever(self):
        t = Tenant.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="orders", name="Órdenes")
        sub = TenantModuleSubscription.objects.create(
            tenant=t, module=m,
            status=TenantModuleSubscription.Status.ACTIVE,
            expires_at=None,
        )
        assert sub.is_active(timezone.now()) is True


class TestActiveModuleCodes:
    """The L1-a gating primitive the resolver will consume in a later slice."""

    def test_returns_only_active_module_codes(self):
        t = Tenant.objects.create(code="acme", name="Acme")
        m_cat = Module.objects.create(code="catalogue", name="Catálogo")
        m_ord = Module.objects.create(code="orders", name="Órdenes")
        m_pos = Module.objects.create(code="pos", name="POS")
        # catalogue: active, no expiry -> included
        TenantModuleSubscription.objects.create(
            tenant=t, module=m_cat,
            status=TenantModuleSubscription.Status.ACTIVE,
        )
        # orders: active but expired -> excluded
        TenantModuleSubscription.objects.create(
            tenant=t, module=m_ord,
            status=TenantModuleSubscription.Status.ACTIVE,
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        # pos: suspended -> excluded
        TenantModuleSubscription.objects.create(
            tenant=t, module=m_pos,
            status=TenantModuleSubscription.Status.SUSPENDED,
        )
        assert t.active_module_codes() == {"catalogue"}

    def test_empty_when_no_subscriptions(self):
        t = Tenant.objects.create(code="acme", name="Acme")
        assert t.active_module_codes() == set()
