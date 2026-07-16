"""Contract for the L1-a company-module gate in ``resolve_capabilities``.

DEC-T7 + SOL-085 S2: a user's L2 capabilities (DEC-11 graded + named) are
**filtered by their Company's active module subscriptions** (L1-a). A
capability only survives if ``capability.module.code`` is in
``user.company.active_module_codes()``.

Boundary: a user with ``company=None`` (L0 cross-company operator or legacy /
unassigned) is **not** gated — the resolver returns caps unchanged. This keeps
the whole existing suite green (``UserFactory`` defaults to ``company=None``).

TDD for the Kaupamex platform base loop (design-first -> construction).
"""
import datetime

import pytest
from django.utils import timezone

from apps.platform.authz.models import (
    AccessLevel,
    Capability,
    DirectEntitlement,
    Module,
    Role,
    RoleAssignment,
    RoleCapability,
)
from apps.platform.authz.services import invalidate_capabilities, resolve_capabilities
from apps.platform.company.models import Company, CompanyModuleSubscription
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


def _grant_graded(user, noun_code, level, module):
    cap = Capability.objects.create(module=module, code=noun_code, name=noun_code)
    role = Role.objects.create(code=f"r-{noun_code}", name=noun_code)
    RoleCapability.objects.create(role=role, capability=cap, level=level)
    RoleAssignment.objects.create(user=user, role=role)
    return cap, role


def _subscribe(company, module, active=True):
    return CompanyModuleSubscription.objects.create(
        company=company, module=module,
        status=(CompanyModuleSubscription.Status.ACTIVE if active
                else CompanyModuleSubscription.Status.SUSPENDED),
    )


class TestCompanyModuleGate:
    def test_no_company_is_no_op(self):
        # company=None -> the gate does not apply; caps resolve unchanged.
        m = Module.objects.create(code="orders", name="Órdenes")
        user = UserFactory()  # company defaults to None
        _grant_graded(user, "orders", AccessLevel.EDIT, m)
        invalidate_capabilities(user.pk)
        caps = resolve_capabilities(user)
        assert {"orders.view", "orders.create", "orders.edit"} <= caps

    def test_active_module_grants_its_caps(self):
        company = Company.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="orders", name="Órdenes")
        _subscribe(company, m, active=True)
        user = UserFactory(company=company)
        _grant_graded(user, "orders", AccessLevel.EDIT, m)
        invalidate_capabilities(user.pk)
        caps = resolve_capabilities(user)
        assert {"orders.view", "orders.create", "orders.edit"} <= caps

    def test_unsubscribed_module_filters_its_caps(self):
        # user belongs to a company that has NOT subscribed the module -> gated out
        company = Company.objects.create(code="acme", name="Acme")
        m_orders = Module.objects.create(code="orders", name="Órdenes")
        m_pos = Module.objects.create(code="pos", name="POS")
        _subscribe(company, m_orders, active=True)  # orders active, pos absent
        user = UserFactory(company=company)
        _grant_graded(user, "orders", AccessLevel.EDIT, m_orders)
        _grant_graded(user, "pos", AccessLevel.FULL, m_pos)
        invalidate_capabilities(user.pk)
        caps = resolve_capabilities(user)
        assert "orders.edit" in caps          # subscribed module survives
        assert not any(c.startswith("pos.") for c in caps)  # unsubscribed gated out

    def test_expired_subscription_filters_its_caps(self):
        company = Company.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="orders", name="Órdenes")
        CompanyModuleSubscription.objects.create(
            company=company, module=m,
            status=CompanyModuleSubscription.Status.ACTIVE,
            expires_at=timezone.now() - datetime.timedelta(days=1),
        )
        user = UserFactory(company=company)
        _grant_graded(user, "orders", AccessLevel.EDIT, m)
        invalidate_capabilities(user.pk)
        caps = resolve_capabilities(user)
        assert not any(c.startswith("orders.") for c in caps)

    def test_company_with_no_active_modules_grants_nothing(self):
        company = Company.objects.create(code="acme", name="Acme")
        m = Module.objects.create(code="orders", name="Órdenes")
        # module exists + granted by role, but the company has NO subscription
        user = UserFactory(company=company)
        _grant_graded(user, "orders", AccessLevel.EDIT, m)
        invalidate_capabilities(user.pk)
        assert resolve_capabilities(user) == set()

    def test_direct_entitlement_is_also_gated(self):
        company = Company.objects.create(code="acme", name="Acme")
        m_pos = Module.objects.create(code="pos", name="POS")
        cap = Capability.objects.create(module=m_pos, code="pos.sell", name="sell")
        user = UserFactory(company=company)  # no pos subscription
        DirectEntitlement.objects.create(user=user, capability=cap)
        invalidate_capabilities(user.pk)
        assert "pos.sell" not in resolve_capabilities(user)
        # now subscribe pos -> the direct entitlement surfaces
        _subscribe(company, m_pos, active=True)
        invalidate_capabilities(user.pk)
        assert "pos.sell" in resolve_capabilities(user)
