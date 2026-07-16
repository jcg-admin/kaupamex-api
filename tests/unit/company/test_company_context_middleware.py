"""Contract for CompanyContextMiddleware (L3, SOL-085).

Puebla ``current_company`` desde ``request.user.company`` durante el request y
lo limpia al salir. El operador L0 (``company=None``) y el anónimo no fijan
scope.
"""
import pytest

from apps.platform.company.context import get_current_company
from apps.platform.company.middleware import CompanyContextMiddleware
from apps.platform.company.models import Company
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


class _Req:
    def __init__(self, user):
        self.user = user


class _AnonUser:
    is_authenticated = False
    company_id = None


def _run(user):
    """Corre el middleware con un get_response que captura el contexto dentro."""
    seen = {}

    def get_response(request):
        seen['company'] = get_current_company()
        return 'ok'

    mw = CompanyContextMiddleware(get_response)
    result = mw(_Req(user))
    return seen['company'], result


class TestCompanyContextMiddleware:
    def test_sets_company_from_authenticated_user(self):
        company = Company.objects.create(code='acme', name='Acme')
        user = UserFactory(company=company)
        seen, result = _run(user)
        assert seen == company.pk
        assert result == 'ok'
        # cleared after the request
        assert get_current_company() is None

    def test_l0_user_without_company_sets_none(self):
        user = UserFactory()  # company defaults to None (L0 / unassigned)
        seen, _ = _run(user)
        assert seen is None
        assert get_current_company() is None

    def test_anonymous_sets_none(self):
        seen, _ = _run(_AnonUser())
        assert seen is None
        assert get_current_company() is None

    def test_context_cleared_even_if_view_raises(self):
        company = Company.objects.create(code='acme', name='Acme')
        user = UserFactory(company=company)

        def boom(request):
            raise ValueError('view error')

        mw = CompanyContextMiddleware(boom)
        with pytest.raises(ValueError):
            mw(_Req(user))
        assert get_current_company() is None  # finally cleared it
