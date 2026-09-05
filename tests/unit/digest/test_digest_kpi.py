"""``digest.digest`` — motor de cómputo de KPIs (addon ``digest``).

Adaptación fiel de Odoo digest/models/digest.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — ``_calculate_company_based_kpi``/
``_compute_kpis``/``_get_margin_value``, con el alcance por compañía
adaptado (ver divergencia 4 de ``addons/digest/models/digest.py``: ni
``ResUsersLog`` ni ``MailMessage`` tienen FK directa a compañía).
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from addons.base.models import ResCompany, ResUsersLog
from addons.digest.models import DigestDigest
from addons.mail.models import MailMessage
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def company_a():
    return ResCompany.objects.create(code='kpi-company-a', name='Compañía A')


@pytest.fixture
def company_b():
    return ResCompany.objects.create(code='kpi-company-b', name='Compañía B')


@pytest.fixture
def user_a(company_a):
    user = UserFactory(login='usuario-a@kaupamex.mx')
    company_a.user_ids.add(user)
    return user


@pytest.fixture
def user_b(company_b):
    user = UserFactory(login='usuario-b@kaupamex.mx')
    company_b.user_ids.add(user)
    return user


@pytest.fixture
def digest(company_a):
    return DigestDigest.objects.create(
        name='Digest KPI', company_id=company_a,
        kpi_res_users_connected=True, kpi_mail_message_total=True,
    )


def _backdate(queryset, when):
    """Los campos ``auto_now_add`` no se pueden fijar en el constructor —
    se retrocede la fecha con un ``UPDATE`` directo, sin pasar por
    ``save()`` (misma técnica usada para poblar rangos de tiempo en
    pruebas de KPI sin depender de ``freezegun``, ausente del proyecto)."""
    queryset.update(created_at=when)


class TestGetMarginValue:
    def test_zero_when_previous_is_zero(self):
        assert DigestDigest._get_margin_value(10, 0.0) == 0.0

    def test_zero_when_equal(self):
        assert DigestDigest._get_margin_value(5, 5) == 0.0

    def test_computes_percentage_increase(self):
        assert DigestDigest._get_margin_value(150, 100) == 50.0

    def test_computes_percentage_decrease(self):
        assert DigestDigest._get_margin_value(50, 100) == -50.0


class TestAvailableFields:
    def test_lists_only_active_kpis(self, company_a):
        digest = DigestDigest.objects.create(
            name='Sólo un KPI', company_id=company_a,
            kpi_res_users_connected=True, kpi_mail_message_total=False,
        )
        assert digest.available_fields == 'kpi_res_users_connected_value'

    def test_empty_when_no_kpi_active(self, company_a):
        digest = DigestDigest.objects.create(name='Sin KPIs', company_id=company_a)
        assert digest.available_fields == ''


class TestComputeKpiResUsersConnectedValue:
    def test_counts_logs_within_range_scoped_by_company(self, digest, user_a, user_b):
        now = timezone.now()
        in_range = ResUsersLog.objects.create(user=user_a)
        _backdate(ResUsersLog.objects.filter(pk=in_range.pk), now - timedelta(hours=1))

        out_of_range = ResUsersLog.objects.create(user=user_a)
        _backdate(ResUsersLog.objects.filter(pk=out_of_range.pk), now - timedelta(days=10))

        other_company = ResUsersLog.objects.create(user=user_b)
        _backdate(ResUsersLog.objects.filter(pk=other_company.pk), now - timedelta(hours=1))

        start, end = now - timedelta(days=1), now
        value = digest._compute_kpi_res_users_connected_value(start, end)
        assert value == 1

    def test_zero_when_no_logs(self, digest):
        now = timezone.now()
        value = digest._compute_kpi_res_users_connected_value(
            now - timedelta(days=1), now,
        )
        assert value == 0


class TestComputeKpiMailMessageTotalValue:
    def test_counts_messages_within_range_scoped_by_company(self, digest, user_a, user_b):
        now = timezone.now()
        own = MailMessage.objects.create(
            author=user_a, model='digest.Digest', res_id=digest.pk,
        )
        _backdate(MailMessage.objects.filter(pk=own.pk), now - timedelta(hours=2))

        foreign = MailMessage.objects.create(
            author=user_b, model='digest.Digest', res_id=digest.pk,
        )
        _backdate(MailMessage.objects.filter(pk=foreign.pk), now - timedelta(hours=2))

        start, end = now - timedelta(days=1), now
        value = digest._compute_kpi_mail_message_total_value(start, end)
        assert value == 1


class TestComputeKpis:
    def test_returns_one_entry_per_active_kpi_with_margin(self, digest, user_a):
        now = timezone.now()
        log = ResUsersLog.objects.create(user=user_a)
        _backdate(ResUsersLog.objects.filter(pk=log.pk), now - timedelta(hours=1))

        kpis = digest.compute_kpis()
        names = {kpi['kpi_name'] for kpi in kpis}
        assert names == {'kpi_res_users_connected', 'kpi_mail_message_total'}

        connected = next(k for k in kpis if k['kpi_name'] == 'kpi_res_users_connected')
        assert connected['kpi_fullname'] == 'Usuarios conectados'
        assert connected['kpi_col1']['value'] == 1
        assert connected['kpi_col1']['col_subtitle'] == 'Últimas 24 horas'

    def test_no_kpis_when_none_active(self, company_a):
        digest = DigestDigest.objects.create(name='Sin KPIs', company_id=company_a)
        assert digest.compute_kpis() == []
