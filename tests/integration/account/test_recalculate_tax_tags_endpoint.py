"""Contrato HTTP de ``POST /api/v2/admin/finance/tax-tags/recalculate/`` —
UC-FIN-11. Cierra H-API-406 para ``account_update_tax_tags`` (tarea #52).
"""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from addons.account.models.account_tax import AccountTax
from addons.authz_reauth.models import ReauthSession
from addons.base.models import ResCompany

RECALCULATE_URL = '/api/v2/admin/finance/tax-tags/recalculate/'

pytestmark = pytest.mark.integration


def _elevate(client, user):
    """DEC-12: ``invoices`` es sensible — sembrar la ventana de
    reautenticación fresca para la sesión ya abierta por ``force_login``."""
    ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key=client.session.session_key or '',
        defaults={'started_at': timezone.now(),
                  'expires_at': timezone.now() + timedelta(seconds=900)})


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme-taxtags', name='ACME TaxTags')


class TestRecalculateTaxTagsHappyPath:
    def test_defaults_date_from_and_reports_no_impact_without_data(
            self, admin_client, admin_user, company):
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            RECALCULATE_URL, {'company_id': company.pk}, format='json')

        assert resp.status_code == 200
        assert resp.data['date_from'] == date.today().isoformat()
        assert resp.data['display_lock_date_warning'] is False
        assert resp.data['impacted_move_line_ids'] == []

    def test_explicit_date_from_is_respected(
            self, admin_client, admin_user, company):
        _elevate(admin_client, admin_user)
        chosen = '2026-01-15'

        resp = admin_client.post(
            RECALCULATE_URL,
            {'company_id': company.pk, 'date_from': chosen}, format='json')

        assert resp.status_code == 200
        assert resp.data['date_from'] == chosen


class TestRecalculateTaxTagsErrors:
    def test_child_tax_shared_by_two_parents_is_422(
            self, admin_client, admin_user, company):
        parent1 = AccountTax.objects.create(name='P1', company=company)
        parent2 = AccountTax.objects.create(name='P2', company=company)
        child = AccountTax.objects.create(name='C', company=company)
        parent1.children.add(child)
        parent2.children.add(child)
        _elevate(admin_client, admin_user)

        resp = admin_client.post(
            RECALCULATE_URL, {'company_id': company.pk}, format='json')

        assert resp.status_code == 422
        assert resp.data['codigo_error'] == 'TAX_TAGS_CHILD_TAX_SHARED'

    def test_without_capability_is_403(self, auth_client, company):
        resp = auth_client.post(
            RECALCULATE_URL, {'company_id': company.pk}, format='json')

        assert resp.status_code == 403
