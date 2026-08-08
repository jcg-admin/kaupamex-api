"""Contrato del núcleo ``account`` — portación fiel del libro mayor de doble
entrada de Odoo (``account``, 18/19).

Cubre cada modelo del paquete:

- ``AccountAccount``: ``internal_group`` derivado de ``account_type`` (Odoo
  ``_compute_internal_group``); ``account_type`` incluye el drift 19
  (``expense_other``, H-ACC-01); único ``(company, code)``.
- ``AccountJournal``: ``type`` enum; único ``(company, code)``.
- ``AccountTax.compute_amount``: el atajo de UN impuesto — percent/fixed/
  division × ``price_include``. El motor de una línea completa (lotes,
  cascada de base, tres pasadas) vive en ``compute_all`` y se prueba en
  ``test_account_tax_compute_all.py``.
- ``AccountMove.post``: invariante de doble entrada (Odoo ``_check_balanced``).
- ``AccountMoveLine``: ``balance = debit - credit`` (Odoo ``_compute_balance``).
- ``AccountPayment``: enums payment_type/partner_type/state.
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from exceptions import UserError
from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
    AccountPayment,
    AccountTax,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


class TestAccountAccount:
    @pytest.mark.parametrize('atype,group', [
        ('asset_receivable', 'asset'),
        ('liability_payable', 'liability'),
        ('equity_unaffected', 'equity'),
        ('income', 'income'),
        ('expense_direct_cost', 'expense'),
        ('off_balance', 'off'),
    ])
    def test_internal_group_derived_from_type(self, company, atype, group):
        acc = AccountAccount.objects.create(
            code='100', name='X', account_type=atype, company=company)
        assert acc.internal_group == group

    def test_expense_other_is_valid_type_19_drift(self, company):
        # H-ACC-01: 19 añade expense_other; se adopta el superset.
        acc = AccountAccount.objects.create(
            code='600', name='Otros gastos', account_type='expense_other',
            company=company)
        assert acc.internal_group == 'expense'

    def test_unique_code_per_company(self, company):
        AccountAccount.objects.create(
            code='100', name='A', account_type='asset_cash', company=company)
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountAccount.objects.create(
                code='100', name='B', account_type='asset_cash', company=company)


class TestAccountJournal:
    def test_type_choices(self, company):
        j = AccountJournal.objects.create(
            name='Ventas', code='VEN', type='sale', company=company)
        assert j.type == 'sale'

    def test_unique_code_per_company(self, company):
        AccountJournal.objects.create(
            name='Ventas', code='VEN', type='sale', company=company)
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountJournal.objects.create(
                name='Otro', code='VEN', type='general', company=company)


class TestAccountTax:
    def test_percent(self, company):
        tax = AccountTax.objects.create(
            name='IVA 16', amount=Decimal('16'), amount_type='percent',
            company=company)
        assert tax.compute_amount(Decimal('100')) == Decimal('16')

    def test_fixed(self, company):
        tax = AccountTax.objects.create(
            name='Cuota', amount=Decimal('5'), amount_type='fixed',
            company=company)
        assert tax.compute_amount(Decimal('100')) == Decimal('5')

    def test_percent_incluido_se_extrae_del_precio(self, company):
        """116 con un 16 % marcado como incluido → 16 contenidos, base 100.

        Éste es el cálculo que el test viejo pedía —y que atribuía a
        ``division``, que es otra cosa (ver el siguiente). ``percent`` +
        ``price_include`` es su nombre correcto (``odoo19c: :88-95``).
        """
        tax = AccountTax.objects.create(
            name='IVA 16 incl', amount=Decimal('16'), amount_type='percent',
            price_include=True, company=company)
        assert tax.compute_amount(Decimal('116')) == pytest.approx(
            Decimal('16'), abs=Decimal('0.0001'))

    def test_division_no_incluido(self, company):
        """``division`` = porcentaje sobre el total CON impuesto.

        El ``help`` de la referencia lo fija con números: *"e.g 180 / (1 - 10%)
        = 200 (not price included)"* — sobre 180 al 10 %, el impuesto es 20,
        no 18. La diferencia con ``percent`` está en el denominador: el
        porcentaje se aplica al total, no a la base.
        """
        tax = AccountTax.objects.create(
            name='Div 10', amount=Decimal('10'), amount_type='division',
            company=company)
        assert tax.compute_amount(Decimal('180')) == pytest.approx(
            Decimal('20'), abs=Decimal('0.0001'))

    def test_division_incluido(self, company):
        """La otra rama del mismo ``help``: *"200 * (1 - 10%) = 180"*.

        Con el precio ya incluyendo el impuesto, el 10 % de 200 son 20 y la
        base queda en 180. El test que este reemplaza calculaba
        ``base - base/(1+amount/100)`` bajo el nombre ``division``: eso es la
        extracción de un *porcentaje* incluido, y daba 16 donde la referencia
        da 18,56 sobre 116 al 16 % (H-API-342).
        """
        tax = AccountTax.objects.create(
            name='Div 10 incl', amount=Decimal('10'), amount_type='division',
            price_include=True, company=company)
        assert tax.compute_amount(Decimal('200')) == pytest.approx(
            Decimal('20'), abs=Decimal('0.0001'))


class TestAccountMoveLine:
    def _move(self, company):
        j = AccountJournal.objects.create(
            name='Varios', code='MISC', type='general', company=company)
        return AccountMove.objects.create(
            date=timezone.now().date(), journal=j, company=company)

    def test_balance_computed_from_debit_credit(self, company):
        move = self._move(company)
        line = AccountMoveLine.objects.create(
            move=move, debit=Decimal('30.00'), credit=Decimal('0.00'))
        assert line.balance == Decimal('30.00')
        line2 = AccountMoveLine.objects.create(
            move=move, debit=Decimal('0.00'), credit=Decimal('12.50'))
        assert line2.balance == Decimal('-12.50')


class TestAccountMovePost:
    def _fixture(self, company):
        j = AccountJournal.objects.create(
            name='Varios', code='MISC', type='general', company=company)
        cash = AccountAccount.objects.create(
            code='101', name='Caja', account_type='asset_cash', company=company)
        income = AccountAccount.objects.create(
            code='401', name='Ventas', account_type='income', company=company)
        move = AccountMove.objects.create(
            date=timezone.now().date(), journal=j, company=company)
        return move, cash, income

    def test_post_balanced_move(self, company):
        move, cash, income = self._fixture(company)
        AccountMoveLine.objects.create(move=move, account=cash, debit=Decimal('100.00'))
        AccountMoveLine.objects.create(move=move, account=income, credit=Decimal('100.00'))
        assert move.is_balanced() is True
        move.post()
        move.refresh_from_db()
        assert move.state == 'posted'
        assert move.amount_total == Decimal('100.00')

    def test_post_unbalanced_rejected(self, company):
        move, cash, income = self._fixture(company)
        AccountMoveLine.objects.create(move=move, account=cash, debit=Decimal('100.00'))
        AccountMoveLine.objects.create(move=move, account=income, credit=Decimal('90.00'))
        with pytest.raises(UserError):
            move.post()
        move.refresh_from_db()
        assert move.state == 'draft'

    def test_post_empty_move_rejected(self, company):
        move, _, _ = self._fixture(company)
        with pytest.raises(UserError):
            move.post()

    def test_button_cancel(self, company):
        move, cash, income = self._fixture(company)
        move.button_cancel()
        move.refresh_from_db()
        assert move.state == 'cancel'


class TestAccountPayment:
    def test_defaults(self, company):
        j = AccountJournal.objects.create(
            name='Banco', code='BNK', type='bank', company=company)
        p = AccountPayment.objects.create(
            amount=Decimal('250.00'), journal=j, company=company)
        assert p.payment_type == 'inbound'
        assert p.partner_type == 'customer'
        assert p.state == 'draft'
        assert p.is_reconciled is False
