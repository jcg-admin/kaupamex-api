"""Contrato de borrado de la conciliación.

``unlink`` de ``account.partial.reconcile``
(``odoo19c: addons/account/models/account_partial_reconcile.py:105-147``) y
de ``account.full.reconcile``
(``odoo19c: addons/account/models/account_full_reconcile.py:47-60``).

Métrica: filas de parciales, conciliaciones totales y apuntes leídas de la
base después de cada ``unlink``.
Ciega a: caja base, diferencia de cambio y pagos, que el parcial no modela
todavía.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountFullReconcile,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
    AccountPartialReconcile,
)
from addons.base.models import ResCompany
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-del', name='ACME Delete')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Varios', code='MISC-D', type='general', company=company
    )


def _line(company, journal, debit=Decimal('0.00'), credit=Decimal('0.00')):
    move = AccountMove.objects.create(
        date=timezone.now().date(), journal=journal, company=company
    )
    return AccountMoveLine.objects.create(
        move=move, debit=debit, credit=credit
    )


def _partials(*pks):
    return AccountPartialReconcile.objects.filter(pk__in=pks)


class TestPartialUnlink:
    def test_only_partial_of_a_full_removes_the_full(self, company, journal):
        debit = _line(company, journal, debit=Decimal('40.00'))
        credit = _line(company, journal, credit=Decimal('40.00'))
        partial = AccountPartialReconcile.create_partial(
            debit, credit, Decimal('40.00')
        )
        full = AccountFullReconcile.create_from_partials(
            _partials(partial.pk)
        )

        partial.unlink()

        assert not AccountFullReconcile.objects.filter(pk=full.pk).exists()
        debit.refresh_from_db()
        credit.refresh_from_db()
        assert debit.full_reconcile_id is None
        assert (debit.matching_number, credit.matching_number) == ('', '')

    def test_one_partial_of_two_breaks_the_full(self, company, journal):
        debit = _line(company, journal, debit=Decimal('50.00'))
        credit1 = _line(company, journal, credit=Decimal('20.00'))
        credit2 = _line(company, journal, credit=Decimal('30.00'))
        first = AccountPartialReconcile.create_partial(
            debit, credit1, Decimal('20.00')
        )
        second = AccountPartialReconcile.create_partial(
            debit, credit2, Decimal('30.00')
        )
        full = AccountFullReconcile.create_from_partials(
            _partials(first.pk, second.pk)
        )

        first.unlink()

        assert not AccountFullReconcile.objects.filter(pk=full.pk).exists()
        assert _partials(first.pk, second.pk).count() == 1
        for line in (debit, credit1, credit2):
            line.refresh_from_db()
        assert credit1.matching_number == ''
        assert debit.matching_number == f'P{second.pk}'
        assert credit2.matching_number == f'P{second.pk}'

    def test_empty_recordset_is_a_no_op(self):
        empty = env()['account.partial.reconcile'].browse()
        assert empty.unlink() is True


class TestFullUnlink:
    def test_full_unlink_keeps_partials_and_renumbers(self, company, journal):
        debit = _line(company, journal, debit=Decimal('15.00'))
        credit = _line(company, journal, credit=Decimal('15.00'))
        partial = AccountPartialReconcile.create_partial(
            debit, credit, Decimal('15.00')
        )
        full = AccountFullReconcile.create_from_partials(
            _partials(partial.pk)
        )

        full.unlink()

        partial.refresh_from_db()
        debit.refresh_from_db()
        assert partial.full_reconcile_id is None
        assert debit.full_reconcile_id is None
        assert debit.matching_number == f'P{partial.pk}'


class TestMoveLineUnlink:
    def test_line_unlink_removes_its_partial(self, company, journal):
        debit = _line(company, journal, debit=Decimal('25.00'))
        credit = _line(company, journal, credit=Decimal('25.00'))
        partial = AccountPartialReconcile.create_partial(
            debit, credit, Decimal('25.00')
        )
        credit.refresh_from_db()
        assert credit.matching_number == f'P{partial.pk}'

        debit.unlink()

        assert not _partials(partial.pk).exists()
        assert not AccountMoveLine.objects.filter(pk=debit.pk).exists()
        credit.refresh_from_db()
        assert credit.matching_number == ''

    def test_line_unlink_breaks_a_full_reconcile(self, company, journal):
        debit = _line(company, journal, debit=Decimal('35.00'))
        credit = _line(company, journal, credit=Decimal('35.00'))
        partial = AccountPartialReconcile.create_partial(
            debit, credit, Decimal('35.00')
        )
        full = AccountFullReconcile.create_from_partials(
            _partials(partial.pk)
        )

        credit.unlink()

        assert not AccountFullReconcile.objects.filter(pk=full.pk).exists()
        debit.refresh_from_db()
        assert debit.full_reconcile_id is None
        assert debit.matching_number == ''

    def test_remove_move_reconcile_keeps_the_lines(self, company, journal):
        debit = _line(company, journal, debit=Decimal('45.00'))
        credit = _line(company, journal, credit=Decimal('45.00'))
        partial = AccountPartialReconcile.create_partial(
            debit, credit, Decimal('45.00')
        )

        (debit + credit).remove_move_reconcile()

        assert not _partials(partial.pk).exists()
        assert AccountMoveLine.objects.filter(
            pk__in=[debit.pk, credit.pk]).count() == 2

    def test_empty_recordset_is_a_no_op(self):
        assert env()['account.move.line'].browse().unlink() is True


class TestMatchedNames:
    """≙ ``matched_debit_ids`` (inverso ``credit_move_id``) y
    ``matched_credit_ids`` (inverso ``debit_move_id``):
    ``odoo19c: addons/account/models/account_move_line.py:262-273``."""

    def test_the_debit_line_reads_its_matched_credits(self, company, journal):
        debit = _line(company, journal, debit=Decimal('55.00'))
        credit = _line(company, journal, credit=Decimal('55.00'))
        partial = AccountPartialReconcile.create_partial(
            debit, credit, Decimal('55.00')
        )

        assert debit.matched_credit_ids.ids == [partial.pk]
        assert not debit.matched_debit_ids
        assert credit.matched_debit_ids.ids == [partial.pk]
        assert not credit.matched_credit_ids
        assert debit.matched_credit_ids.credit_move == credit
