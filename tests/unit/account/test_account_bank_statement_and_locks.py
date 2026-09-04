"""Contrato de extractos y candados — portación fiel de Odoo ``account`` (19c).

Cubre:

- ``AccountCashRounding``: ``round()``/``compute_difference()`` (Odoo
  ``round``/``compute_difference``, estrategias UP/DOWN/HALF-UP).
- ``AccountIncoterms``: creación + ``__str__`` (Odoo ``_compute_display_name``).
- ``AccountJournalGroup``: único ``(company, name)`` (Odoo ``_uniq_name``).
- ``AccountLockException``: ``state`` derivado (active/revoked/expired) y
  ``applies_to()`` (sustituto de los computados ``*_lock_date`` de la
  referencia — ver docstring de ``account_lock_exception.py``).
- ``AccountBankStatement``/``AccountBankStatementLine``: ``_inherits`` de
  ``account.move`` (delegación por propiedad), ``recompute()``,
  ``internal_index`` (orden invertido de ``sequence``), ``running_balance``
  (ancla + SQL crudo, incluyendo la rama multi-empresa vía ``parent_path``
  — H-API-330) e ``is_valid`` (camino directo + camino buscable con
  ventana ``LAG`` — H-API-321).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from addons.account.models import (
    AccountBankStatement,
    AccountBankStatementLine,
    AccountCashRounding,
    AccountIncoterms,
    AccountJournal,
    AccountJournalGroup,
    AccountLockException,
    AccountMove,
)
from addons.base.models import ResCompany, ResUsers
from exceptions import UserError

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def user():
    return ResUsers.objects.create_user(login='candados@kaupamex.test', password='x')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Banco', code='BNK', type='bank', company=company)


class TestAccountCashRounding:
    def test_round_half_up(self, company):
        profile = AccountCashRounding.objects.create(
            name='CHF 0.05', rounding=Decimal('0.05'),
            rounding_method=AccountCashRounding.METHOD_HALF_UP)
        assert profile.round(Decimal('23.93')) == Decimal('23.95')

    def test_round_down(self, company):
        profile = AccountCashRounding.objects.create(
            name='Down', rounding=Decimal('0.05'),
            rounding_method=AccountCashRounding.METHOD_DOWN)
        assert profile.round(Decimal('23.94')) == Decimal('23.90')

    def test_compute_difference(self, company):
        profile = AccountCashRounding.objects.create(
            name='CHF 0.05', rounding=Decimal('0.05'),
            rounding_method=AccountCashRounding.METHOD_HALF_UP)
        # Odoo docstring: base_amount=23.91, redondeado=23.90 -> diff=-0.01
        assert profile.compute_difference(Decimal('23.91')) == Decimal('-0.01')


class TestAccountIncoterms:
    def test_create_and_str(self):
        term = AccountIncoterms.objects.create(name='Free on Board', code='FOB')
        assert str(term) == '[FOB] Free on Board'


class TestAccountJournalGroup:
    def test_unique_name_per_company(self, company):
        AccountJournalGroup.objects.create(name='Grupo A', company=company)
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountJournalGroup.objects.create(name='Grupo A', company=company)


class TestAccountLockException:
    def test_state_active_by_default(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='sale_lock_date')
        assert exc.state == AccountLockException.STATE_ACTIVE

    def test_state_revoked_after_revoke(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='sale_lock_date')
        exc.revoke()
        assert exc.state == AccountLockException.STATE_REVOKED

    def test_state_expired_past_end_datetime(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='sale_lock_date',
            end_datetime=timezone.now() - timedelta(days=1))
        assert exc.state == AccountLockException.STATE_EXPIRED

    def test_applies_to_matching_field(self, company):
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='purchase_lock_date',
            lock_date='2026-01-01')
        assert exc.applies_to('purchase_lock_date') == exc.lock_date
        assert exc.applies_to('sale_lock_date') is None


class TestResCompanyLockDates:
    """``ResCompany.get_user_lock_date`` y su API — H-API-320, tarea #110.

    Cierra el computado que ``account_lock_exception.py`` declaraba
    pendiente: el candado vigente para un usuario combina el campo crudo de
    ``ResCompany`` con la excepción vigente más favorable.
    """

    def test_no_lock_date_set_returns_date_min(self, company):
        assert company.get_user_sale_lock_date() == date.min

    def test_raw_company_lock_date_without_exception(self, company):
        company.sale_lock_date = date(2026, 1, 31)
        company.save(update_fields=['sale_lock_date'])
        assert company.get_user_sale_lock_date() == date(2026, 1, 31)

    def test_global_exception_moves_lock_date_earlier_for_any_user(
            self, company, user):
        company.purchase_lock_date = date(2026, 3, 31)
        company.save(update_fields=['purchase_lock_date'])
        AccountLockException.objects.create(
            company=company, lock_date_field='purchase_lock_date',
            lock_date=date(2026, 2, 15))
        assert company.get_user_purchase_lock_date(user=user) == date(2026, 2, 15)
        assert company.get_user_purchase_lock_date(user=None) == date(2026, 2, 15)

    def test_user_scoped_exception_does_not_apply_to_other_user(
            self, company, user):
        other_user = ResUsers.objects.create_user(
            login='otro@kaupamex.test', password='x')
        company.tax_lock_date = date(2026, 4, 30)
        company.save(update_fields=['tax_lock_date'])
        AccountLockException.objects.create(
            company=company, user=user, lock_date_field='tax_lock_date',
            lock_date=date(2026, 3, 1))
        assert company.get_user_tax_lock_date(user=user) == date(2026, 3, 1)
        assert company.get_user_tax_lock_date(user=other_user) == date(2026, 4, 30)

    def test_ignore_exceptions_returns_raw_company_date(self, company, user):
        company.fiscalyear_lock_date = date(2026, 1, 31)
        company.save(update_fields=['fiscalyear_lock_date'])
        AccountLockException.objects.create(
            company=company, lock_date_field='fiscalyear_lock_date',
            lock_date=date(2025, 12, 1))
        assert company.get_user_fiscalyear_lock_date(
            user=user, ignore_exceptions=True) == date(2026, 1, 31)

    def test_revoked_exception_does_not_apply(self, company, user):
        company.sale_lock_date = date(2026, 5, 31)
        company.save(update_fields=['sale_lock_date'])
        exc = AccountLockException.objects.create(
            company=company, lock_date_field='sale_lock_date',
            lock_date=date(2026, 4, 1))
        exc.revoke()
        assert company.get_user_sale_lock_date() == date(2026, 5, 31)

    def test_hard_lock_date_has_no_exceptions(self, company):
        company.hard_lock_date = date(2026, 6, 30)
        company.save(update_fields=['hard_lock_date'])
        assert company.get_user_hard_lock_date() == date(2026, 6, 30)

    def test_hard_lock_date_without_value_returns_date_min(self, company):
        assert company.get_user_hard_lock_date() == date.min

    def test_violated_soft_lock_date_before_lock(self, company):
        company.sale_lock_date = date(2026, 1, 31)
        company.save(update_fields=['sale_lock_date'])
        violated = company.get_violated_soft_lock_date(
            'sale_lock_date', date(2026, 1, 15))
        assert violated == date(2026, 1, 31)

    def test_violated_soft_lock_date_after_lock_is_none(self, company):
        company.sale_lock_date = date(2026, 1, 31)
        company.save(update_fields=['sale_lock_date'])
        violated = company.get_violated_soft_lock_date(
            'sale_lock_date', date(2026, 2, 15))
        assert violated is None

    def test_get_lock_date_violations_aggregates_soft_and_hard(self, company):
        company.sale_lock_date = date(2026, 1, 31)
        company.hard_lock_date = date(2026, 1, 15)
        company.save(update_fields=['sale_lock_date', 'hard_lock_date'])
        violations = company.get_lock_date_violations(date(2026, 1, 10))
        fields_hit = {field for _, field in violations}
        assert fields_hit == {'sale_lock_date', 'hard_lock_date'}

    def test_get_violated_lock_dates_respects_journal_type(
            self, company, journal):
        sale_journal = AccountJournal.objects.create(
            name='Ventas', code='SAL', type='sale', company=company)
        company.sale_lock_date = date(2026, 1, 31)
        company.purchase_lock_date = date(2026, 1, 31)
        company.save(update_fields=['sale_lock_date', 'purchase_lock_date'])

        locks_sale = company.get_violated_lock_dates(
            date(2026, 1, 10), has_tax=False, journal=sale_journal)
        fields_sale = {field for _, field in locks_sale}
        assert 'sale_lock_date' in fields_sale
        assert 'purchase_lock_date' not in fields_sale

        # ``journal`` (fixture) es type='bank': ni venta ni compra se chequean.
        locks_bank = company.get_violated_lock_dates(
            date(2026, 1, 10), has_tax=False, journal=journal)
        fields_bank = {field for _, field in locks_bank}
        assert 'sale_lock_date' not in fields_bank
        assert 'purchase_lock_date' not in fields_bank

    def test_format_lock_dates_includes_verbose_name_and_date(self, company):
        formatted = company.format_lock_dates(
            [(date(2026, 1, 31), 'sale_lock_date')])
        assert 'Candado de ventas' in formatted
        assert '2026-01-31' in formatted

    def test_validate_hard_lock_date_change_noop_when_unset(self, company):
        company.validate_hard_lock_date_change(date(2026, 1, 1))

    def test_validate_hard_lock_date_change_rejects_removal(self, company):
        company.hard_lock_date = date(2026, 1, 31)
        with pytest.raises(UserError):
            company.validate_hard_lock_date_change(None)

    def test_validate_hard_lock_date_change_rejects_earlier_date(self, company):
        company.hard_lock_date = date(2026, 1, 31)
        with pytest.raises(UserError):
            company.validate_hard_lock_date_change(date(2026, 1, 1))

    def test_validate_hard_lock_date_change_accepts_later_date(self, company):
        company.hard_lock_date = date(2026, 1, 31)
        company.validate_hard_lock_date_change(date(2026, 2, 28))


class TestAccountBankStatement:
    def test_line_delegates_to_move(self, company, journal):
        move = AccountMove.objects.create(
            company=company, journal=journal, date='2026-01-15')
        line = AccountBankStatementLine.objects.create(
            move=move, amount=Decimal('150.00'), payment_ref='Depósito')
        assert line.journal == journal
        assert line.company == company
        assert line.date == move.date
        assert line.state == 'draft'

    def test_recompute_balance_and_completeness(self, company, journal):
        move = AccountMove.objects.create(
            company=company, journal=journal, date='2026-01-15', state='posted')
        statement = AccountBankStatement.objects.create(
            company=company, journal=journal,
            balance_start=Decimal('100.00'), balance_end_real=Decimal('250.00'))
        AccountBankStatementLine.objects.create(
            move=move, statement=statement, amount=Decimal('150.00'))
        statement.recompute()
        assert statement.balance_end == Decimal('250.00')
        assert statement.is_complete is True

    def test_internal_index_orders_lower_sequence_first_same_date(
            self, company, journal):
        """``internal_index`` invierte ``sequence`` (Odoo
        ``_compute_internal_index``, odoo19c:258-280): aunque el ``order``
        por defecto del modelo es ``-internal_index`` (descendente), una
        ``sequence`` más baja sigue apareciendo primero — el mismo criterio
        de prioridad ascendente que el resto de campos ``sequence`` de
        Odoo. Cubre también el formato del índice (28 = 8 fecha + 10
        secuencia + 10 id)."""
        move_low = AccountMove.objects.create(
            company=company, journal=journal, date='2026-02-01')
        move_high = AccountMove.objects.create(
            company=company, journal=journal, date='2026-02-01')
        line_low = AccountBankStatementLine.objects.create(
            move=move_low, amount=Decimal('10.00'), sequence=1)
        line_high = AccountBankStatementLine.objects.create(
            move=move_high, amount=Decimal('20.00'), sequence=5)

        ordered = list(AccountBankStatementLine.objects.filter(
            pk__in=[line_low.pk, line_high.pk]))
        assert [line.pk for line in ordered] == [line_low.pk, line_high.pk]

        assert len(line_low.internal_index) == 28
        assert line_low.internal_index.startswith('20260201')
        assert line_low.internal_index > line_high.internal_index

    def test_running_balance_accumulates_over_three_lines(
            self, company, journal):
        """``running_balance`` (Odoo ``_compute_running_balance``, odoo19c:
        178-256, NO ``store``): sin estado de cuenta previo, ancla en 0.00
        y acumula secuencialmente sólo las líneas posteadas."""
        move1 = AccountMove.objects.create(
            company=company, journal=journal, date='2026-02-01',
            state='posted')
        move2 = AccountMove.objects.create(
            company=company, journal=journal, date='2026-02-02',
            state='posted')
        move3 = AccountMove.objects.create(
            company=company, journal=journal, date='2026-02-03',
            state='posted')
        line1 = AccountBankStatementLine.objects.create(
            move=move1, amount=Decimal('100.00'))
        line2 = AccountBankStatementLine.objects.create(
            move=move2, amount=Decimal('-30.00'))
        line3 = AccountBankStatementLine.objects.create(
            move=move3, amount=Decimal('50.00'))

        assert line1.running_balance == Decimal('100.00')
        assert line2.running_balance == Decimal('70.00')
        assert line3.running_balance == Decimal('120.00')

    def test_running_balance_anchors_to_previous_statement(
            self, company, journal):
        """El acumulado ancla en el ``balance_start`` del último estado de
        cuenta anterior al lote (odoo19c: account_bank_statement_line.py:
        199-217) — una línea sin estado propio, posterior a un estado ya
        cerrado, sigue acumulando desde ahí, no desde cero."""
        move1 = AccountMove.objects.create(
            company=company, journal=journal, date='2026-02-10',
            state='posted')
        statement1 = AccountBankStatement.objects.create(
            company=company, journal=journal, balance_start=Decimal('100.00'))
        line1 = AccountBankStatementLine.objects.create(
            move=move1, statement=statement1, amount=Decimal('50.00'))
        statement1.recompute()
        statement1.save()

        move2 = AccountMove.objects.create(
            company=company, journal=journal, date='2026-02-11',
            state='posted')
        line2 = AccountBankStatementLine.objects.create(
            move=move2, amount=Decimal('20.00'))

        assert line1.running_balance == Decimal('150.00')
        assert line2.running_balance == Decimal('170.00')

    def test_running_balance_multicompany_includes_children_not_siblings(
            self, journal):
        """H-API-330 (tarea #125): ``_compute_running_balances`` ancla en la
        empresa del primer registro de línea que trae la consulta y expande
        esa ancla a sus descendientes vía ``parent_path`` — equivalente al
        ``child_of`` de la referencia (odoo19c:
        account_bank_statement_line.py:178-256, ``company2children``).
        Empresa matriz + filial: el acumulado de una línea de la MATRIZ
        suma también las líneas de la FILIAL (descendiente). Una tercera
        empresa SIN relación (ni ancestro ni descendiente de la matriz) NO
        debe sumarse, aunque su transacción caiga cronológicamente entre
        las de la matriz y la filial."""
        parent_company = ResCompany.objects.create(
            code='hold-p125', name='Holding P125')
        child_company = ResCompany.objects.create(
            code='sub-p125', name='Filial P125', parent=parent_company)
        unrelated_company = ResCompany.objects.create(
            code='oth-p125', name='Otra empresa P125')

        move_child = AccountMove.objects.create(
            company=child_company, journal=journal, date='2026-04-01',
            state='posted')
        move_unrelated = AccountMove.objects.create(
            company=unrelated_company, journal=journal, date='2026-04-02',
            state='posted')
        move_parent = AccountMove.objects.create(
            company=parent_company, journal=journal, date='2026-04-03',
            state='posted')

        line_child = AccountBankStatementLine.objects.create(
            move=move_child, amount=Decimal('50.00'))
        line_unrelated = AccountBankStatementLine.objects.create(
            move=move_unrelated, amount=Decimal('9999.00'))
        line_parent = AccountBankStatementLine.objects.create(
            move=move_parent, amount=Decimal('100.00'))

        # La filial, aislada: no tiene descendientes propios, así que sólo
        # se ve a sí misma.
        assert line_child.running_balance == Decimal('50.00')

        # La empresa sin relación, aislada de ambas.
        assert line_unrelated.running_balance == Decimal('9999.00')

        # La matriz suma su propia línea + la de la filial (descendiente),
        # NUNCA la de la empresa sin relación — aunque sea cronológicamente
        # anterior a la de la matriz.
        assert line_parent.running_balance == Decimal('150.00')

    def test_is_valid_true_and_false_cases(self, company, journal):
        """``is_valid`` — caso válido (primer estado del diario) y caso
        inválido (``balance_start`` no coincide con el ``balance_end_real``
        del estado anterior), cubriendo ambos caminos: el directo
        (``_compute_is_valid``, odoo19c:196-207) y el buscable/lote con
        ventana ``LAG`` (``_get_invalid_statement_ids``/``_search_is_valid``,
        odoo19c:219-223,242-275)."""
        move1 = AccountMove.objects.create(
            company=company, journal=journal, date='2026-03-01',
            state='posted')
        statement1 = AccountBankStatement.objects.create(
            company=company, journal=journal,
            balance_start=Decimal('0.00'), balance_end_real=Decimal('50.00'))
        AccountBankStatementLine.objects.create(
            move=move1, statement=statement1, amount=Decimal('50.00'))
        statement1.recompute()
        statement1.save()
        assert statement1.is_valid is True

        move2 = AccountMove.objects.create(
            company=company, journal=journal, date='2026-03-02',
            state='posted')
        statement2 = AccountBankStatement.objects.create(
            company=company, journal=journal,
            balance_start=Decimal('999.00'),
            balance_end_real=Decimal('1000.00'))
        AccountBankStatementLine.objects.create(
            move=move2, statement=statement2, amount=Decimal('1.00'))
        statement2.recompute()
        statement2.save()
        assert statement2.is_valid is False

        invalid_ids = set(AccountBankStatement._get_invalid_statement_ids(
            all_statements=True))
        assert statement2.pk in invalid_ids
        assert statement1.pk not in invalid_ids

        valid_pks = set(
            AccountBankStatement._search_is_valid('in', True)
            .values_list('pk', flat=True))
        assert statement1.pk in valid_pks
        assert statement2.pk not in valid_pks

        # La otra rama: `is_valid in [False]` devuelve los invalidos. La
        # referencia no la tiene —siempre devuelve `not in invalid_ids`— y
        # por eso esta declarada como divergencia en el docstring del metodo.
        invalid_pks = set(
            AccountBankStatement._search_is_valid('in', False)
            .values_list('pk', flat=True))
        assert statement2.pk in invalid_pks
        assert statement1.pk not in invalid_pks

    def test_search_is_valid_refuses_an_operator_it_cannot_honour(self):
        """La guarda de la fuente (``odoo19c: :220-221``): solo ``in``.

        Devolver un queryset ante un operador que no sabemos resolver seria
        peor que rehusar — pareceria una respuesta. La referencia devuelve
        ``NotImplemented`` y aqui igual.
        """
        assert AccountBankStatement._search_is_valid('=') is NotImplemented
        assert AccountBankStatement._search_is_valid('not in') is NotImplemented

    def test_the_three_line_indexes_exist(self):
        """Los tres índices que dependen de ``internal_index``
        (``_main_idx``/``_unreconciled_idx``/``_orphan_idx``, odoo19c:
        account_bank_statement_line.py:151-153) están realmente creados en
        PostgreSQL — no sólo declarados en ``Meta``."""
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT indexname FROM pg_indexes WHERE tablename = %s',
                ['account_bank_statement_line'])
            names = {row[0] for row in cursor.fetchall()}
        assert 'acc_bank_stmt_line_main_idx' in names
        assert 'acc_bank_stmt_line_unrecon_idx' in names
        assert 'acc_bank_stmt_line_orphan_idx' in names
