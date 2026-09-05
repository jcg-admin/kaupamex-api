"""``digest.digest`` — motor de suscripción, estado y periodicidad (addon
``digest``, cierre parcial — sin motor de envío, ver
``addons/digest/models/digest.py``).

Adaptación fiel de Odoo digest/models/digest.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from addons.base.models import ResCompany, ResGroups
from addons.digest.models import DigestDigest, DigestPeriodicity, DigestState
from exceptions import ValidationError
from orm.environments import user_scope
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-digest', name='ACME')


@pytest.fixture
def internal_group():
    return ResGroups.objects.create(name='Interno', user_type=ResGroups.USER_TYPE_INTERNAL)


@pytest.fixture
def internal_user(internal_group):
    user = UserFactory(login='ana@kaupamex.mx')
    internal_group.user_ids.add(user)
    return user


@pytest.fixture
def digest(company):
    return DigestDigest.objects.create(name='Digest diario', company_id=company)


class TestDigestNextRunDate:
    def test_save_computes_next_run_date_on_create_when_absent(self, digest):
        assert digest.next_run_date == timezone.localdate() + timedelta(days=1)

    def test_next_run_date_respects_explicit_value(self, company):
        explicit = timezone.localdate() + timedelta(days=30)
        digest = DigestDigest.objects.create(
            name='Digest con fecha fija', company_id=company, next_run_date=explicit,
        )
        assert digest.next_run_date == explicit

    def test_action_set_periodicity_recomputes_next_run_date(self, digest):
        digest.action_set_periodicity(DigestPeriodicity.WEEKLY)
        assert digest.periodicity == DigestPeriodicity.WEEKLY
        assert digest.next_run_date == timezone.localdate() + timedelta(weeks=1)

    def test_action_set_periodicity_monthly_uses_calendar_month(self, digest):
        digest.action_set_periodicity(DigestPeriodicity.MONTHLY)
        expected_month = (timezone.localdate().month % 12) + 1
        assert digest.next_run_date.month == expected_month

    def test_action_set_periodicity_rejects_invalid_value(self, digest):
        with pytest.raises(ValidationError):
            digest.action_set_periodicity('yearly')

    def test_get_next_periodicity_progression(self, digest):
        assert digest._get_next_periodicity() == DigestPeriodicity.WEEKLY
        digest.periodicity = DigestPeriodicity.WEEKLY
        assert digest._get_next_periodicity() == DigestPeriodicity.MONTHLY
        digest.periodicity = DigestPeriodicity.MONTHLY
        assert digest._get_next_periodicity() == DigestPeriodicity.QUARTERLY
        digest.periodicity = DigestPeriodicity.QUARTERLY
        assert digest._get_next_periodicity() == DigestPeriodicity.QUARTERLY


class TestDigestState:
    def test_action_activate_sets_state(self, digest):
        digest.action_deactivate()
        digest.action_activate()
        digest.refresh_from_db()
        assert digest.state == DigestState.ACTIVATED

    def test_action_deactivate_sets_state(self, digest):
        digest.action_deactivate()
        digest.refresh_from_db()
        assert digest.state == DigestState.DEACTIVATED


class TestDigestSubscription:
    def test_is_subscribed_false_without_current_user(self, digest):
        assert digest.is_subscribed is False

    def test_action_subscribe_adds_current_internal_user(self, digest, internal_user):
        with user_scope(internal_user.pk):
            digest.action_subscribe()
        assert digest.user_ids.filter(pk=internal_user.pk).exists()

    def test_is_subscribed_true_after_subscribe(self, digest, internal_user):
        digest.user_ids.add(internal_user)
        with user_scope(internal_user.pk):
            assert digest.is_subscribed is True

    def test_action_subscribe_noop_for_share_user(self, digest):
        share_user = UserFactory(login='publico@kaupamex.mx')
        assert share_user.share is True
        with user_scope(share_user.pk):
            digest.action_subscribe()
        assert not digest.user_ids.filter(pk=share_user.pk).exists()

    def test_action_unsubscribe_removes_user(self, digest, internal_user):
        digest.user_ids.add(internal_user)
        with user_scope(internal_user.pk):
            digest.action_unsubscribe()
        assert not digest.user_ids.filter(pk=internal_user.pk).exists()


class TestDigestCurrency:
    def test_currency_property_reads_company_currency(self, digest, company):
        assert digest.currency == company.currency

    def test_currency_property_none_without_company(self):
        digest = DigestDigest.objects.create(name='Sin compañía', company_id=None)
        assert digest.currency is None


class TestDigestStr:
    def test_str_returns_name(self, digest):
        assert str(digest) == 'Digest diario'
