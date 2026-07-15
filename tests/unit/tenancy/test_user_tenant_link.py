"""Contract for the user<->tenant (L1) link.

``IdentityUser.tenant`` is a nullable FK to ``tenancy.Tenant``: L1 users belong
to one tenant; L0 operators (superadmin/platform-operator) and legacy/unassigned
users keep ``tenant=None`` (cross-tenant). Slice 2 adds only the schema link —
the resolver L1 filter that consumes it comes later.
"""
import pytest
from django.db.models import ProtectedError

from apps.tenancy.models import Tenant
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


class TestUserTenantLink:
    def test_user_defaults_to_no_tenant(self):
        # existing behaviour preserved: a user needs no tenant (L0 / unassigned)
        u = UserFactory()
        assert u.tenant is None

    def test_user_can_belong_to_a_tenant(self):
        t = Tenant.objects.create(code="acme", name="Acme")
        u = UserFactory(tenant=t)
        assert u.tenant == t
        assert list(t.users.all()) == [u]

    def test_tenant_with_users_is_protected(self):
        t = Tenant.objects.create(code="acme", name="Acme")
        UserFactory(tenant=t)
        with pytest.raises(ProtectedError):
            t.delete()
