"""Contract for the module dependency graph (SOL-085 S3, decoupled from the
``modules/`` reorg — SOL-083 not done, so the ``manifest.py`` file convention is
deferred; the behaviourally meaningful piece is the ``Module.depends`` graph).

DEC-T7 + the addon-organization analysis: activating a module for a company
requires its declared dependencies to be **already active** for that company
(e.g. POS depends on inventory + catalogue). Enforced at the subscription level
so the invariant can't be bypassed. Direct-dep checking is transitively correct:
you could not have activated ``inventory`` without ``core`` active, so checking
``pos``'s direct deps at activation transitively guarantees the closure.

TDD for the Kaupamex platform base loop (design-first -> construction).
"""
import pytest
from django.core.exceptions import ValidationError

from addons.authz.models import Module
from addons.platform.models import Company, CompanyModuleSubscription

pytestmark = pytest.mark.django_db


def _module(code, depends=()):
    m = Module.objects.create(code=code, name=code)
    if depends:
        m.depends.set(depends)
    return m


class TestModuleDependencyGraph:
    def test_module_has_no_deps_by_default(self):
        m = _module("catalogue")
        assert list(m.depends.all()) == []

    def test_declares_dependencies(self):
        cat = _module("catalogue")
        inv = _module("inventory")
        pos = _module("pos", depends=[cat, inv])
        assert set(pos.depends.values_list("code", flat=True)) == {"catalogue", "inventory"}
        # reverse accessor (dependents)
        assert set(cat.dependents.values_list("code", flat=True)) == {"pos"}


class TestActivationGuard:
    def test_missing_dependency_blocks_active_subscription(self):
        company = Company.objects.create(code="acme", name="Acme")
        cat = _module("catalogue")
        pos = _module("pos", depends=[cat])
        # catalogue NOT active for the company -> activating pos must fail
        with pytest.raises(ValidationError):
            CompanyModuleSubscription.objects.create(
                company=company, module=pos,
                status=CompanyModuleSubscription.Status.ACTIVE,
            )

    def test_active_dependency_allows_active_subscription(self):
        company = Company.objects.create(code="acme", name="Acme")
        cat = _module("catalogue")
        pos = _module("pos", depends=[cat])
        # subscribe catalogue first (active) -> then pos activates fine
        CompanyModuleSubscription.objects.create(
            company=company, module=cat,
            status=CompanyModuleSubscription.Status.ACTIVE,
        )
        sub = CompanyModuleSubscription.objects.create(
            company=company, module=pos,
            status=CompanyModuleSubscription.Status.ACTIVE,
        )
        assert sub.pk is not None
        assert company.active_module_codes() == {"catalogue", "pos"}

    def test_inactive_subscription_skips_dependency_check(self):
        company = Company.objects.create(code="acme", name="Acme")
        cat = _module("catalogue")
        pos = _module("pos", depends=[cat])
        # a SUSPENDED (not active) pos subscription is allowed without catalogue
        sub = CompanyModuleSubscription.objects.create(
            company=company, module=pos,
            status=CompanyModuleSubscription.Status.SUSPENDED,
        )
        assert sub.pk is not None
        assert company.active_module_codes() == set()

    def test_missing_dependencies_helper_lists_the_gap(self):
        company = Company.objects.create(code="acme", name="Acme")
        cat = _module("catalogue")
        inv = _module("inventory")
        pos = _module("pos", depends=[cat, inv])
        CompanyModuleSubscription.objects.create(
            company=company, module=cat,
            status=CompanyModuleSubscription.Status.ACTIVE,
        )
        # only inventory is missing (catalogue is active)
        pending = CompanyModuleSubscription(
            company=company, module=pos,
            status=CompanyModuleSubscription.Status.ACTIVE,
        )
        assert pending.missing_dependencies() == {"inventory"}
