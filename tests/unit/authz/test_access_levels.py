"""Contract for DEC-11 graduated access levels (NetSuite VIEW<CREATE<EDIT<FULL).

The authz core moves from a flat Role↔Capability M2M to a graded
``RoleCapability`` through-model carrying an ``AccessLevel``. The grade is the
source of truth; ``resolve_capabilities`` expands a noun's level into the
implied ``noun.verb`` code set so existing call-sites (126 required_capability
declarations) and the dynamic menu keep working unchanged.

TDD for the "generar los grupos" slice (T-PLT-31; DEC-11 ratified 2026-07-11).
"""
import pytest

from apps.authz.models import (
    AccessLevel,
    Capability,
    Module,
    Role,
    RoleAssignment,
    RoleCapability,
)
from apps.authz.services import (
    has_capability,
    invalidate_capabilities,
    resolve_capabilities,
    resolve_capability_levels,
)
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


class TestAccessLevelScale:
    def test_levels_are_graduated(self):
        assert AccessLevel.NONE < AccessLevel.VIEW < AccessLevel.CREATE \
            < AccessLevel.EDIT < AccessLevel.FULL

    def test_verb_maps_to_level(self):
        # the .verb suffix a call-site uses maps to a required level
        assert AccessLevel.for_verb("view") == AccessLevel.VIEW
        assert AccessLevel.for_verb("create") == AccessLevel.CREATE
        assert AccessLevel.for_verb("edit") == AccessLevel.EDIT
        # legacy ".manage" (old top of the 2-level model) == FULL
        assert AccessLevel.for_verb("manage") == AccessLevel.FULL
        assert AccessLevel.for_verb("full") == AccessLevel.FULL


def _grant(user, noun_code, level, module):
    cap = Capability.objects.create(module=module, code=noun_code, name=noun_code)
    role = Role.objects.create(code=f"r-{noun_code}", name=noun_code)
    RoleCapability.objects.create(role=role, capability=cap, level=level)
    RoleAssignment.objects.create(user=user, role=role)
    invalidate_capabilities(user.pk)
    return cap, role


class TestLevelExpansion:
    def test_edit_expands_to_lower_verbs(self):
        m = Module.objects.create(code="sales", name="Sales")
        user = UserFactory()
        _grant(user, "orders", AccessLevel.EDIT, m)
        caps = resolve_capabilities(user)
        # EDIT implies view+create+edit, NOT the top grade
        assert "orders.view" in caps
        assert "orders.create" in caps
        assert "orders.edit" in caps
        assert "orders.full" not in caps

    def test_has_capability_respects_required_level(self):
        m = Module.objects.create(code="sales", name="Sales")
        user = UserFactory()
        _grant(user, "orders", AccessLevel.VIEW, m)
        assert has_capability(user, "orders.view") is True
        # VIEW grant does not satisfy a .manage (FULL) requirement
        assert has_capability(user, "orders.manage") is False

    def test_levels_map_returns_max_across_roles(self):
        m = Module.objects.create(code="sales", name="Sales")
        user = UserFactory()
        cap = Capability.objects.create(module=m, code="orders", name="orders")
        r1 = Role.objects.create(code="r1", name="r1")
        r2 = Role.objects.create(code="r2", name="r2")
        RoleCapability.objects.create(role=r1, capability=cap, level=AccessLevel.VIEW)
        RoleCapability.objects.create(role=r2, capability=cap, level=AccessLevel.FULL)
        RoleAssignment.objects.create(user=user, role=r1)
        RoleAssignment.objects.create(user=user, role=r2)
        invalidate_capabilities(user.pk)
        # the higher grade wins
        assert resolve_capability_levels(user)["orders"] == AccessLevel.FULL
        assert has_capability(user, "orders.manage") is True


class TestNamedActionsUnchanged:
    def test_named_action_is_membership_not_graded(self):
        m = Module.objects.create(code="acct", name="Account")
        user = UserFactory()
        # a named-action capability (not a CRUD verb) is granted at FULL and
        # matched by exact membership, no level ladder
        _grant(user, "account.profile", AccessLevel.FULL, m)
        assert has_capability(user, "account.profile") is True
        assert has_capability(user, "account.password") is False
