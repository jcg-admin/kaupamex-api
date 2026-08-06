"""Contrato de ``account.payment.method(.line)`` y ``account.payment.term(.line)``
— portación fiel de Odoo ``account_payment_method.py``/``account_payment_term.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``).

Cubre:

- ``AccountPaymentMethod``: único ``(code, payment_type)``,
  ``_get_payment_method_information``, cascada de líneas al borrar.
- ``AccountPaymentMethodLine``: ``_compute_name`` (nombre por defecto del
  método), propiedades ``code``/``payment_type``/``company``/
  ``default_account`` (Odoo ``related``).
- ``AccountPaymentTerm``: ``_check_lines`` (suma de porcentajes 100%,
  pronto pago sólo con línea única), ``_get_amount_due_after_discount``,
  ``_compute_terms`` (distribución de cuotas), ``_get_amount_by_date``,
  ``_get_last_discount_date``.
- ``AccountPaymentTermLine``: ``_get_due_date`` (los 4 ``delay_type``, sin
  ``dateutil`` — ver docstring de ``account_payment_term.py``),
  ``_check_valid_char_value``/``_check_percent`` (gate en ``save()``),
  ``display_days_next_month``.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from exceptions import ValidationError
from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountPaymentMethod,
    AccountPaymentMethodLine,
    AccountPaymentTerm,
    AccountPaymentTermLine,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-pay', name='ACME Pay')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNK2', type='bank', company=company)


class TestAccountPaymentMethod:
    def test_defaults(self):
        m = AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='inbound')
        assert m.payment_type == 'inbound'

    def test_unique_code_payment_type(self):
        AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='inbound')
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountPaymentMethod.objects.create(
                name='Manual otra vez', code='manual', payment_type='inbound')

    def test_same_code_different_payment_type_allowed(self):
        # (code, payment_type) es la unicidad — mismo code, distinto type: OK.
        AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='inbound')
        m2 = AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='outbound')
        assert m2.pk is not None

    def test_get_payment_method_information(self):
        m = AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='inbound')
        info = m._get_payment_method_information()
        assert info['manual']['mode'] == 'multi'
        assert info['manual']['type'] == ('bank', 'cash', 'credit')

    def test_delete_cascades_lines(self, journal):
        m = AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='inbound')
        line = AccountPaymentMethodLine.objects.create(
            payment_method=m, journal=journal)
        line_pk = line.pk
        m.delete()
        assert not AccountPaymentMethodLine.objects.filter(pk=line_pk).exists()


class TestAccountPaymentMethodLine:
    def test_name_defaults_to_method_name(self, journal):
        m = AccountPaymentMethod.objects.create(
            name='Transferencia', code='manual', payment_type='inbound')
        line = AccountPaymentMethodLine.objects.create(
            payment_method=m, journal=journal)
        assert line.name == 'Transferencia'

    def test_name_explicit_not_overridden(self, journal):
        m = AccountPaymentMethod.objects.create(
            name='Transferencia', code='manual', payment_type='inbound')
        line = AccountPaymentMethodLine.objects.create(
            payment_method=m, journal=journal, name='Transferencia SPEI')
        assert line.name == 'Transferencia SPEI'

    def test_related_properties(self, company, journal):
        m = AccountPaymentMethod.objects.create(
            name='Manual', code='manual', payment_type='outbound')
        line = AccountPaymentMethodLine.objects.create(
            payment_method=m, journal=journal)
        assert line.code == 'manual'
        assert line.payment_type == 'outbound'
        assert line.company == company
        assert line.default_account == journal.default_account


class TestAccountPaymentTermCheckLines:
    def test_single_line_100_percent_valid(self, company):
        term = AccountPaymentTerm.objects.create(name='Contado', company=company)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('100'))
        term._check_lines()  # no debe lanzar

    def test_sum_not_100_raises(self, company):
        term = AccountPaymentTerm.objects.create(name='30/70 malo', company=company)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('30'))
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('60'))
        with pytest.raises(ValidationError):
            term._check_lines()

    def test_early_discount_multiple_lines_raises(self, company):
        term = AccountPaymentTerm.objects.create(
            name='2/10 malo', company=company, early_discount=True,
            discount_percentage=Decimal('2'), discount_days=10)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('30'))
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('70'))
        with pytest.raises(ValidationError):
            term._check_lines()


class TestAccountPaymentTermDiscount:
    def test_get_amount_due_after_discount_included(self, company):
        term = AccountPaymentTerm.objects.create(
            name='2/10 Net 30', company=company, early_discount=True,
            discount_percentage=Decimal('2'), discount_days=10,
            early_pay_discount_computation='included')
        due = term._get_amount_due_after_discount(
            Decimal('1000'), Decimal('1000'))
        assert due == Decimal('980.00')

    def test_get_amount_due_after_discount_disabled(self, company):
        term = AccountPaymentTerm.objects.create(name='Net 30', company=company)
        due = term._get_amount_due_after_discount(
            Decimal('1000'), Decimal('1000'))
        assert due == Decimal('1000')

    def test_get_last_discount_date(self, company):
        term = AccountPaymentTerm.objects.create(
            name='2/10 Net 30', company=company, early_discount=True,
            discount_days=10)
        assert term._get_last_discount_date(date(2026, 1, 1)) == date(2026, 1, 11)

    def test_get_last_discount_date_disabled(self, company):
        term = AccountPaymentTerm.objects.create(name='Net 30', company=company)
        assert term._get_last_discount_date(date(2026, 1, 1)) is False


class TestAccountPaymentTermComputeTerms:
    def test_two_installments_30_70(self, company):
        term = AccountPaymentTerm.objects.create(name='30/70', company=company)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('30'),
            delay_type='days_after', nb_days=0)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('70'),
            delay_type='days_after', nb_days=30)

        currency = term.currency
        result = term._compute_terms(
            date_ref=date(2026, 1, 1), currency=currency,
            tax_amount=Decimal('0'), tax_amount_currency=Decimal('0'),
            sign=1, untaxed_amount=Decimal('1000'),
            untaxed_amount_currency=Decimal('1000'))

        assert result['total_amount'] == Decimal('1000')
        assert len(result['line_ids']) == 2
        first, second = result['line_ids']
        assert first['company_amount'] == Decimal('300.00')
        assert first['date'] == date(2026, 1, 1)
        # La última línea es siempre la línea de saldo (Odoo _compute_terms):
        # su importe es el residual, no su value_amount declarado.
        assert second['company_amount'] == Decimal('700.00')
        assert second['date'] == date(2026, 1, 31)
        assert first['company_amount'] + second['company_amount'] == Decimal('1000')

    def test_fixed_line_then_balance(self, company):
        term = AccountPaymentTerm.objects.create(name='Fijo + saldo', company=company)
        AccountPaymentTermLine.objects.create(
            payment=term, value='fixed', value_amount=Decimal('250'),
            delay_type='days_after', nb_days=15)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('100'),
            delay_type='days_after', nb_days=45)

        currency = term.currency
        result = term._compute_terms(
            date_ref=date(2026, 1, 1), currency=currency,
            tax_amount=Decimal('0'), tax_amount_currency=Decimal('0'),
            sign=1, untaxed_amount=Decimal('1000'),
            untaxed_amount_currency=Decimal('1000'))
        first, second = result['line_ids']
        assert first['company_amount'] == Decimal('250.00')
        assert second['company_amount'] == Decimal('750.00')

    def test_get_amount_by_date_groups(self, company):
        term = AccountPaymentTerm.objects.create(name='30/70', company=company)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('30'), nb_days=0)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('70'), nb_days=30)
        currency = term.currency
        terms = term._compute_terms(
            date_ref=date(2026, 1, 1), currency=currency,
            tax_amount=Decimal('0'), tax_amount_currency=Decimal('0'),
            sign=1, untaxed_amount=Decimal('1000'),
            untaxed_amount_currency=Decimal('1000'))
        by_date = term._get_amount_by_date(terms)
        assert len(by_date) == 2
        assert by_date[date(2026, 1, 1)]['amount'] == Decimal('300.00')
        assert by_date[date(2026, 1, 31)]['amount'] == Decimal('700.00')


class TestAccountPaymentTermLineDueDate:
    def _line(self, **kwargs):
        term = AccountPaymentTermLine(**kwargs)
        return term

    def test_days_after(self):
        line = self._line(delay_type='days_after', nb_days=15)
        assert line._get_due_date(date(2026, 1, 1)) == date(2026, 1, 16)

    def test_days_after_end_of_month(self):
        line = self._line(delay_type='days_after_end_of_month', nb_days=0)
        # Enero 2026 tiene 31 días.
        assert line._get_due_date(date(2026, 1, 5)) == date(2026, 1, 31)

    def test_days_after_end_of_month_with_offset(self):
        line = self._line(delay_type='days_after_end_of_month', nb_days=5)
        assert line._get_due_date(date(2026, 1, 5)) == date(2026, 2, 5)

    def test_days_after_end_of_next_month(self):
        line = self._line(delay_type='days_after_end_of_next_month', nb_days=0)
        # Fin del mes siguiente a enero 2026 → 28 de febrero 2026.
        assert line._get_due_date(date(2026, 1, 5)) == date(2026, 2, 28)

    def test_days_end_of_month_on_the(self):
        line = self._line(
            delay_type='days_end_of_month_on_the', nb_days=0, days_next_month='10')
        # due_date (sin offset) + 1 mes calendario, día fijo = 10.
        assert line._get_due_date(date(2026, 1, 5)) == date(2026, 2, 10)

    def test_days_end_of_month_on_the_zero_means_end_of_month(self):
        line = self._line(
            delay_type='days_end_of_month_on_the', nb_days=0, days_next_month='0')
        assert line._get_due_date(date(2026, 1, 5)) == date(2026, 1, 31)

    def test_january_31_plus_one_month_clamps_to_february(self):
        # El caso de overflow que dateutil.relativedelta resuelve con
        # clamping — replicado con stdlib (ver docstring del módulo).
        line = self._line(delay_type='days_after_end_of_next_month', nb_days=0)
        assert line._get_due_date(date(2026, 1, 31)) == date(2026, 2, 28)


class TestAccountPaymentTermLineValidation:
    def test_check_percent_out_of_range_raises_on_save(self, company):
        term = AccountPaymentTerm.objects.create(name='Malo', company=company)
        with pytest.raises(ValidationError):
            AccountPaymentTermLine.objects.create(
                payment=term, value='percent', value_amount=Decimal('150'))

    def test_check_valid_char_value_raises_on_save(self, company):
        term = AccountPaymentTerm.objects.create(name='Malo', company=company)
        with pytest.raises(ValidationError):
            AccountPaymentTermLine.objects.create(
                payment=term, value='percent', value_amount=Decimal('100'),
                delay_type='days_end_of_month_on_the', days_next_month='99')

    def test_display_days_next_month(self, company):
        term = AccountPaymentTerm.objects.create(name='OK', company=company)
        line_a = AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('100'),
            delay_type='days_after')
        assert line_a.display_days_next_month is False
        line_b = AccountPaymentTermLine.objects.create(
            payment=term, value='fixed', value_amount=Decimal('0'),
            delay_type='days_end_of_month_on_the', days_next_month='15')
        assert line_b.display_days_next_month is True


class TestAccountPaymentTermLineSiblingComputations:
    def test_compute_days_from_previous_sibling(self, company):
        term = AccountPaymentTerm.objects.create(name='Escalera', company=company)
        first = AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('50'), nb_days=10)
        second = AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('50'), nb_days=0)
        second.nb_days = 0
        second._compute_days()
        assert second.nb_days == first.nb_days + 30

    def test_compute_value_amount_percent_fills_remainder(self, company):
        term = AccountPaymentTerm.objects.create(name='Resto', company=company)
        AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('30'))
        third = AccountPaymentTermLine.objects.create(
            payment=term, value='percent', value_amount=Decimal('100'))
        third._compute_value_amount()
        assert third.value_amount == Decimal('70')

    def test_compute_value_amount_fixed_is_zero(self, company):
        term = AccountPaymentTerm.objects.create(name='Fijo', company=company)
        line = AccountPaymentTermLine.objects.create(
            payment=term, value='fixed', value_amount=Decimal('250'))
        line._compute_value_amount()
        assert line.value_amount == Decimal('0')
