"""Contract for the user<->company (L1) link.

``IdentityUser.company`` is a nullable FK to ``company.Company``: L1 users belong
to one company; L0 operators (superadmin/platform-operator) and legacy/unassigned
users keep ``company=None`` (cross-company). Slice 2 adds only the schema link —
the resolver L1 filter that consumes it comes later.
"""
import pytest
from django.db.models import ProtectedError

from addons.platform.models import Company
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


class TestUserCompanyLink:
    def test_user_defaults_to_no_company(self):
        # existing behaviour preserved: a user needs no company (L0 / unassigned)
        u = UserFactory()
        assert u.company is None

    def test_user_can_belong_to_a_company(self):
        t = Company.objects.create(code="acme", name="Acme")
        u = UserFactory(company=t)
        assert u.company == t
        assert list(t.users.all()) == [u]

    def test_company_with_users_is_protected(self):
        t = Company.objects.create(code="acme", name="Acme")
        UserFactory(company=t)
        with pytest.raises(ProtectedError):
            t.delete()
