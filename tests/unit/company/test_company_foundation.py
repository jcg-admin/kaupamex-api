"""Contract for the Company/L1 foundation (plataforma-kaupamex, capa L1).

Design: ``docs/source/gestion/pm/api/iniciativas/plataforma-kaupamex/
analisis-modelo-company-l1-foundation.rst`` — ``Company`` (L1 root) +
``CompanyModuleSubscription`` (per-module billing/gating) reusing the existing
``authz.Module`` pivot (L1<->L2). Slice 1: models + the L1-a "active module
codes" primitive **in isolation** — NOT yet wired into ``authz.services.
resolve_capabilities`` (that needs a user<->company link, a later slice), so the
existing suite stays green.

TDD for the Kaupamex platform base loop (design-first -> construction).
"""
import datetime

import pytest
from django.db import IntegrityError
from django.utils import timezone

from addons.authz.models import Module
from addons.company.models import Company, CompanyModuleSubscription

pytestmark = pytest.mark.django_db


class TestCompanyModel:
    def test_create_and_str(self):
        # code distinto de FOUNDER_COMPANY_CODE ('practicayoruba'): esa fila
        # ya existe, sembrada por la migración de datos
        # company/0006_seed_founder_settings (SOL-090 slice 3) con sus
        # CompanySetting L3 — este test sólo verifica la creación/str/default
        # genéricos, no la identidad del tenant founder (ver
        # test_founder_system_company.py para eso).
        t = Company.objects.create(code="wonka-basic", name="Wonka")
        assert str(t) == "wonka-basic"
        # default status is TRIAL (a company is born on trial until activated)
        assert t.status == Company.Status.TRIAL

    def test_code_is_unique(self):
        Company.objects.create(code="acme", name="Acme")
        with pytest.raises(IntegrityError):
            Company.objects.create(code="acme", name="Acme 2")


class TestCompanyModuleSubscription:
    def test_unique_per_company_module(self):
        t = Company.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="catalogue", name="Catálogo")
        CompanyModuleSubscription.objects.create(company=t, module=m)
        with pytest.raises(IntegrityError):
            CompanyModuleSubscription.objects.create(company=t, module=m)

    def test_is_active_respects_status_and_expiry(self):
        t = Company.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="orders", name="Órdenes")
        now = timezone.now()
        active = CompanyModuleSubscription.objects.create(
            company=t, module=m,
            status=CompanyModuleSubscription.Status.ACTIVE,
            expires_at=now + datetime.timedelta(days=30),
        )
        assert active.is_active(now) is True

        active.expires_at = now - datetime.timedelta(days=1)
        assert active.is_active(now) is False  # expired

        active.expires_at = None
        active.status = CompanyModuleSubscription.Status.SUSPENDED
        assert active.is_active(now) is False  # suspended never active

    def test_no_expiry_means_active_forever(self):
        t = Company.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="orders", name="Órdenes")
        sub = CompanyModuleSubscription.objects.create(
            company=t, module=m,
            status=CompanyModuleSubscription.Status.ACTIVE,
            expires_at=None,
        )
        assert sub.is_active(timezone.now()) is True


class TestActiveModuleCodes:
    """The L1-a gating primitive the resolver will consume in a later slice."""

    def test_returns_only_active_module_codes(self):
        t = Company.objects.create(code="acme", name="Acme")
        m_cat = Module.objects.create(code="catalogue", name="Catálogo")
        m_ord = Module.objects.create(code="orders", name="Órdenes")
        m_pos = Module.objects.create(code="pos", name="POS")
        # catalogue: active, no expiry -> included
        CompanyModuleSubscription.objects.create(
            company=t, module=m_cat,
            status=CompanyModuleSubscription.Status.ACTIVE,
        )
        # orders: active but expired -> excluded
        CompanyModuleSubscription.objects.create(
            company=t, module=m_ord,
            status=CompanyModuleSubscription.Status.ACTIVE,
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        # pos: suspended -> excluded
        CompanyModuleSubscription.objects.create(
            company=t, module=m_pos,
            status=CompanyModuleSubscription.Status.SUSPENDED,
        )
        assert t.active_module_codes() == {"catalogue"}

    def test_empty_when_no_subscriptions(self):
        t = Company.objects.create(code="acme", name="Acme")
        assert t.active_module_codes() == set()
