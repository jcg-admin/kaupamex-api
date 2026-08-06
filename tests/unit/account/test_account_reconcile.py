"""Contrato de conciliación — ``account.partial.reconcile`` /
``account.full.reconcile`` / ``account.reconcile.model[.line]``.

Portación fiel de ``account_partial_reconcile.py`` / ``account_full_reconcile.py``
/ ``account_reconcile_model.py`` (Odoo 19; odoo-tools@622ddc2a). Cubre:

- ``AccountPartialReconcile._update_matching_number``: algoritmo de unión de
  grafos (dos partials sobre 3 apuntes comparten número; un partial suelto
  tiene su propio número).
- ``AccountFullReconcile.create_from_partials``: reemplaza el ``'P<n>'``
  parcial por el id del full reconcile en las líneas agrupadas.
- Baja de un partial/full: recalcula ``matching_number`` de lo que sobrevive.
- ``AccountReconcileModel``: enums, validación de regex, ``compute_can_be_proposed``.
- ``AccountReconcileModelLine``: ``amount`` derivado de ``amount_string``,
  ``company`` sincronizado desde ``model.company`` (related+store=True),
  validación por ``amount_type``.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from exceptions import UserError
from addons.account.models import (
    AccountAccount,
    AccountFullReconcile,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
    AccountPartialReconcile,
    AccountReconcileModel,
    AccountReconcileModelLine,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-rec', name='ACME Reconcile')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Varios', code='MISC-R', type='general', company=company)


def _line(company, journal, debit=Decimal('0.00'), credit=Decimal('0.00')):
    move = AccountMove.objects.create(
        date=timezone.now().date(), journal=journal, company=company)
    return AccountMoveLine.objects.create(move=move, debit=debit, credit=credit)


class TestAccountPartialReconcile:
    def test_two_partials_share_matching_number(self, company, journal):
        # Un apunte deudor de 100 emparejado con dos acreedores de 60 y 40:
        # las tres líneas deben terminar con el MISMO matching_number
        # (unión de grafos: comparten un nodo -> mismo grupo).
        debit = _line(company, journal, debit=Decimal('100.00'))
        credit_a = _line(company, journal, credit=Decimal('60.00'))
        credit_b = _line(company, journal, credit=Decimal('40.00'))

        AccountPartialReconcile.create_partial(debit, credit_a, Decimal('60.00'))
        AccountPartialReconcile.create_partial(debit, credit_b, Decimal('40.00'))

        debit.refresh_from_db()
        credit_a.refresh_from_db()
        credit_b.refresh_from_db()
        assert debit.matching_number
        assert debit.matching_number == credit_a.matching_number
        assert debit.matching_number == credit_b.matching_number

    def test_unrelated_partial_gets_its_own_number(self, company, journal):
        debit1 = _line(company, journal, debit=Decimal('50.00'))
        credit1 = _line(company, journal, credit=Decimal('50.00'))
        debit2 = _line(company, journal, debit=Decimal('20.00'))
        credit2 = _line(company, journal, credit=Decimal('20.00'))

        AccountPartialReconcile.create_partial(debit1, credit1, Decimal('50.00'))
        AccountPartialReconcile.create_partial(debit2, credit2, Decimal('20.00'))

        debit1.refresh_from_db()
        debit2.refresh_from_db()
        assert debit1.matching_number != debit2.matching_number

    def test_max_date_is_latest_of_the_two_moves(self, company, journal):
        debit = _line(company, journal, debit=Decimal('10.00'))
        credit = _line(company, journal, credit=Decimal('10.00'))
        partial = AccountPartialReconcile.create_partial(debit, credit, Decimal('10.00'))
        assert partial.max_date == max(debit.move.date, credit.move.date)

    def test_unlink_recomputes_matching_number(self, company, journal):
        debit = _line(company, journal, debit=Decimal('30.00'))
        credit = _line(company, journal, credit=Decimal('30.00'))
        partial = AccountPartialReconcile.create_partial(debit, credit, Decimal('30.00'))

        partial.delete_and_update_matching()

        debit.refresh_from_db()
        credit.refresh_from_db()
        assert debit.matching_number == ''
        assert credit.matching_number == ''


class TestAccountFullReconcile:
    def test_create_from_partials_stamps_full_reconcile_id_as_number(self, company, journal):
        debit = _line(company, journal, debit=Decimal('75.00'))
        credit = _line(company, journal, credit=Decimal('75.00'))
        partial = AccountPartialReconcile.create_partial(debit, credit, Decimal('75.00'))

        full = AccountFullReconcile.create_from_partials(
            AccountPartialReconcile.objects.filter(pk=partial.pk))

        debit.refresh_from_db()
        credit.refresh_from_db()
        partial.refresh_from_db()
        assert debit.full_reconcile_id == full.pk
        assert credit.full_reconcile_id == full.pk
        assert debit.matching_number == str(full.pk)
        assert credit.matching_number == str(full.pk)
        assert partial.full_reconcile_id == full.pk

    def test_delete_full_reconcile_falls_back_to_partial_number(self, company, journal):
        debit = _line(company, journal, debit=Decimal('12.00'))
        credit = _line(company, journal, credit=Decimal('12.00'))
        partial = AccountPartialReconcile.create_partial(debit, credit, Decimal('12.00'))
        full = AccountFullReconcile.create_from_partials(
            AccountPartialReconcile.objects.filter(pk=partial.pk))

        full.delete_and_update_matching()

        debit.refresh_from_db()
        credit.refresh_from_db()
        assert debit.matching_number == f'P{partial.pk}'
        assert debit.matching_number == credit.matching_number


class TestAccountReconcileModel:
    def test_defaults(self, company):
        model = AccountReconcileModel.objects.create(name='Regla banco', company=company)
        assert model.active is True
        assert model.trigger == 'manual'
        assert model.can_be_proposed is False

    def test_invalid_label_regex_rejected(self, company):
        with pytest.raises(UserError):
            AccountReconcileModel.objects.create(
                name='Regla mala', company=company,
                match_label='match_regex', match_label_param='(unclosed',
            )

    def test_compute_can_be_proposed_true_when_auto_reconcile(self, company):
        model = AccountReconcileModel.objects.create(
            name='Auto', company=company, trigger='auto_reconcile')
        assert model.compute_can_be_proposed() is True

    def test_set_manual_and_auto_reconcile(self, company):
        model = AccountReconcileModel.objects.create(name='Toggle', company=company)
        model.set_auto_reconcile()
        model.refresh_from_db()
        assert model.trigger == 'auto_reconcile'
        model.set_manual()
        model.refresh_from_db()
        assert model.trigger == 'manual'


class TestAccountReconcileModelLine:
    def _model(self, company):
        return AccountReconcileModel.objects.create(name='Regla', company=company)

    def test_amount_parsed_from_amount_string(self, company):
        model = self._model(company)
        line = AccountReconcileModelLine.objects.create(
            model=model, amount_type='percentage', amount_string='55')
        assert line.amount == 55.0

    def test_company_synced_from_model(self, company):
        model = self._model(company)
        line = AccountReconcileModelLine.objects.create(
            model=model, amount_type='percentage', amount_string='100')
        assert line.company_id == company.pk

    def test_zero_percentage_rejected(self, company):
        model = self._model(company)
        with pytest.raises(UserError):
            AccountReconcileModelLine.objects.create(
                model=model, amount_type='percentage', amount_string='0')

    def test_invalid_regex_amount_rejected(self, company):
        model = self._model(company)
        with pytest.raises(UserError):
            AccountReconcileModelLine.objects.create(
                model=model, amount_type='regex', amount_string='(unclosed')

    def test_mapped_partner_requires_single_partner_only_line(self, company):
        model = self._model(company)
        model.match_label = 'contains'
        model.save(update_fields=['match_label'])
        account = AccountAccount.objects.create(
            code='999-R', name='Cuenta', account_type='asset_cash', company=company)
        AccountReconcileModelLine.objects.create(
            model=model, amount_type='percentage', amount_string='100',
            account=account,
        )
        # Con account_id fijo (no sólo partner), no cuenta como mapeo de partner.
        assert model.compute_mapped_partner() is None
