"""Contract for the CompanyScopedManager core primitive (SOL-085 L3 core).

En MariaDB 11.8 no hay RLS tipo Postgres, así que el aislamiento de fila L3 se
hace a nivel de aplicación: un ``current_company`` (ContextVar) fija la company
del request y ``CompanyScopedManager.for_current_company()`` filtra por ella,
**fail-closed** (sin company en contexto → queryset vacío, nunca "todo").

Este slice entrega el **núcleo** (contextvar + manager) con
``CompanyModuleSubscription`` como primer consumidor real (ya tiene FK company;
sin migración). El rollout a los modelos de dominio + el middleware
subdominio→company (UC-PLT-06) + la system-company son la iniciativa L3 mayor.
"""
import pytest

from apps.platform.authz.models import Module
from apps.platform.company.context import (
    company_scope,
    get_current_company,
    set_current_company,
)
from apps.platform.company.models import Company, CompanyModuleSubscription

pytestmark = pytest.mark.django_db


class TestCurrentCompanyContext:
    def test_defaults_to_none(self):
        assert get_current_company() is None

    def test_set_and_get(self):
        set_current_company(42)
        try:
            assert get_current_company() == 42
        finally:
            set_current_company(None)

    def test_company_scope_contextmanager_sets_and_restores(self):
        assert get_current_company() is None
        with company_scope(7):
            assert get_current_company() == 7
        assert get_current_company() is None  # restored on exit


class TestCompanyScopedManager:
    def _sub(self, company, code):
        m = Module.objects.create(code=code, name=code)
        return CompanyModuleSubscription.objects.create(
            company=company, module=m,
            status=CompanyModuleSubscription.Status.ACTIVE,
        )

    def test_for_current_company_scopes_rows(self):
        acme = Company.objects.create(code="acme", name="Acme")
        globex = Company.objects.create(code="globex", name="Globex")
        self._sub(acme, "catalogue")
        self._sub(globex, "orders")
        with company_scope(acme.pk):
            rows = CompanyModuleSubscription.scoped.for_current_company()
            assert {r.company_id for r in rows} == {acme.pk}
            assert rows.count() == 1

    def test_fail_closed_when_no_company_in_context(self):
        acme = Company.objects.create(code="acme", name="Acme")
        self._sub(acme, "catalogue")
        # no company set -> empty (deny by default), NOT all rows
        assert get_current_company() is None
        assert CompanyModuleSubscription.scoped.for_current_company().count() == 0

    def test_default_manager_is_unscoped(self):
        # the default manager still sees everything (L0 cross-company access)
        acme = Company.objects.create(code="acme", name="Acme")
        globex = Company.objects.create(code="globex", name="Globex")
        self._sub(acme, "catalogue")
        self._sub(globex, "orders")
        assert CompanyModuleSubscription.objects.count() == 2
