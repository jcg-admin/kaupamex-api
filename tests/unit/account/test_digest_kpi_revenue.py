"""``account/models/digest.py::_compute_kpi_account_total_revenue_value`` —
el KPI de ingresos del digest (tarea #279).

Adaptación de ``odoo19c: addons/account/models/digest.py:14-27`` (LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Se ejerce por la puerta que el árbol usa de verdad —
``digest.compute_kpi_value('kpi_account_total_revenue', start, end)``, que
despacha al método instalado por ``extend_model`` — y no llamando a la
función de módulo: así un ``metodos=`` mal cableado se nota aquí.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount, AccountJournal, AccountMove, AccountMoveLine,
)
from addons.account.models.digest import GROUP_ACCOUNT_INVOICE
from addons.base.models import ResCompany
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from addons.digest.models import DigestDigest
from exceptions import AccessError
from orm.environments import user_scope
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db

TODAY = timezone.now().date()
START = TODAY - timedelta(days=7)
END = TODAY


@pytest.fixture
def company():
    return ResCompany.objects.create(
        code='digest-revenue-co', name='Digest Revenue Co')


@pytest.fixture
def digest(company):
    return DigestDigest.objects.create(
        name='Digest con ingresos', company_id=company)


@pytest.fixture
def invoicing_user():
    """Un usuario dentro de ``account.group_account_invoice``."""
    user = UserFactory(login='facturacion@practicayoruba.mx')
    group = ResGroups.objects.create(name='Facturación (fixture)')
    IrModelData.set_xmlid(group, GROUP_ACCOUNT_INVOICE)
    user.group_ids.add(group)
    return user


@pytest.fixture
def outsider():
    return UserFactory(login='ajeno@practicayoruba.mx')


def _post_income(company, amount, on=None, post=True, account_type='income'):
    """Un asiento con una línea de caja y una de la cuenta ``account_type``
    por ``amount``; publicado salvo ``post=False``."""
    journal = AccountJournal.objects.create(
        name='Varios', code='MISC', type='general', company=company)
    cash = AccountAccount.objects.create(
        code='101', name='Caja', account_type='asset_cash', company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type=account_type, company=company)
    move = AccountMove.objects.create(
        date=on or TODAY, journal=journal, company=company)
    AccountMoveLine.objects.create(move=move, account=cash, debit=amount)
    AccountMoveLine.objects.create(move=move, account=income, credit=amount)
    if post:
        move.post()
    return move


class TestRevenueIsTheNegatedIncomeBalance:
    """≙ ``record.kpi_account_total_revenue_value =
    -total_per_companies.get(company, 0)``."""

    def test_posted_income_in_window_is_counted_positive(
        self, digest, company, invoicing_user,
    ):
        _post_income(company, Decimal('100.00'))
        with user_scope(invoicing_user.pk):
            value = digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
        # El crédito deja balance -100; la fuente lo niega para mostrarlo.
        assert value == Decimal('100.00')

    def test_no_income_gives_zero_not_none(
        self, digest, company, invoicing_user,
    ):
        with user_scope(invoicing_user.pk):
            value = digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
        assert value == 0

    def test_draft_move_is_not_counted(self, digest, company, invoicing_user):
        """``parent_state = 'posted'`` — aquí ``move__state``."""
        _post_income(company, Decimal('100.00'), post=False)
        with user_scope(invoicing_user.pk):
            value = digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
        assert value == 0

    def test_non_income_account_is_not_counted(
        self, digest, company, invoicing_user,
    ):
        """``account_id.internal_group = 'income'`` — una cuenta de gasto
        deja ``internal_group='expense'`` y queda fuera."""
        _post_income(company, Decimal('100.00'), account_type='expense')
        with user_scope(invoicing_user.pk):
            value = digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
        assert value == 0

    def test_other_company_is_not_counted(
        self, digest, company, invoicing_user,
    ):
        other = ResCompany.objects.create(
            code='digest-revenue-other', name='Otra Co')
        _post_income(other, Decimal('100.00'))
        with user_scope(invoicing_user.pk):
            value = digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
        assert value == 0


class TestWindowIsOpenAtStartAndClosedAtEnd:
    """``('date', '>', start)`` y ``('date', '<=', end)`` — verbatim de la
    fuente (``:22-23``), no el ``>= / <`` del genérico."""

    def test_move_dated_exactly_at_start_is_excluded(
        self, digest, company, invoicing_user,
    ):
        _post_income(company, Decimal('100.00'), on=START)
        with user_scope(invoicing_user.pk):
            value = digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
        assert value == 0

    def test_move_dated_exactly_at_end_is_included(
        self, digest, company, invoicing_user,
    ):
        _post_income(company, Decimal('100.00'), on=END)
        with user_scope(invoicing_user.pk):
            value = digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
        assert value == Decimal('100.00')


class TestAccessGuard:
    """≙ ``if not self.env.user.has_group('account.group_account_invoice'):
    raise AccessError(...)``."""

    def test_user_outside_the_group_is_refused(
        self, digest, company, outsider,
    ):
        with user_scope(outsider.pk), pytest.raises(AccessError):
            digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)

    def test_no_current_user_is_refused_not_a_crash(self, digest, company):
        with user_scope(None), pytest.raises(AccessError):
            digest.compute_kpi_value(
                'kpi_account_total_revenue', START, END)
