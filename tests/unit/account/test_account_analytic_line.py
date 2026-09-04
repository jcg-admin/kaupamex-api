"""``account`` sobre ``account.analytic.line`` (tarea #520).

El conector ``move_line`` se construyó en esta tarea
(``addons/analytic/migrations/`` en el alcance) — desbloquea 3 de los 11
``def`` de la referencia: ``_compute_general_account_id``,
``_check_general_account_id``, ``_compute_analytic_profitability``. Los
otros 8 quedan sin cambio (ver docstring de ``account_analytic_line.py``):
``journal``/``_compute_partner_id`` — BLOQUEADO de segundo orden
(``account.move.line`` no declara ``journal``/``partner``, archivo fuera de
alcance); ``create``/``write``/``unlink`` — BLOQUEADO (``analytic_
distribution`` ausente); ``on_change_unit_amount``/``view_header_get``/
``_field_to_sql``/``_search_analytic_profitability`` — divergencia de
mecanismo, sin cambio.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_analytic_line import apply_account_extensions
from addons.account.models.account_journal import AccountJournal
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.analytic.models import (
    AccountAnalyticAccount, AccountAnalyticLine, AccountAnalyticPlan,
)
from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def apply_extension():
    """Idempotente — segura de invocar en cada test aunque otro módulo ya la
    haya aplicado en el mismo proceso."""
    apply_account_extensions()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Diario', code='GEN', type='general', company=company)


@pytest.fixture
def move(company, journal):
    return AccountMove.objects.create(
        company=company, date=datetime.date.today(), journal=journal)


@pytest.fixture
def expense_account(company):
    return AccountAccount.objects.create(
        code='60100', name='Compras', account_type='expense', company=company)


@pytest.fixture
def analytic_account():
    """El campo ``account`` (``AnalyticPlanFieldsMixin``) que
    ``clean()`` exige SIEMPRE — distinto de ``general_account`` (el que
    ``account`` cuelga en este archivo). Sin él, ``clean()`` levanta
    ``ANALYTIC_LINE_ACCOUNT_REQUIRED`` antes de llegar a la validación
    nueva."""
    plan = AccountAnalyticPlan.objects.create(name='Plan')
    return AccountAnalyticAccount.objects.create(name='Cuenta analitica', plan=plan)


@pytest.fixture
def move_line(move, expense_account):
    return AccountMoveLine.objects.create(
        move=move, account=expense_account, debit=Decimal('100.00'))


class TestTheFieldsWereApplied:
    def test_move_line_general_account_product_code_ref_exist_as_columns(self):
        columns = {f.column for f in AccountAnalyticLine._meta.fields}
        assert {
            'move_line_id', 'general_account_id', 'product_id', 'code', 'ref',
        } <= columns

    def test_analytic_profitability_creates_no_column(self):
        """``store=False`` — no aparece en ``_meta.get_fields()``."""
        columns = {f.column for f in AccountAnalyticLine._meta.fields}
        assert 'analytic_profitability' not in columns
        assert hasattr(AccountAnalyticLine, 'analytic_profitability')

    def test_category_choices_include_invoice_and_vendor_bill(self):
        field = AccountAnalyticLine._meta.get_field('category')
        values = {value for value, _ in field.choices}
        assert {'invoice', 'vendor_bill'} <= values
        assert 'other' in values


class TestGeneralAccountDerivedFromMoveLine:
    """≙ ``_compute_general_account_id`` (odoo19c: :62-65)."""

    def test_it_derives_general_account_from_move_line_account(self, company, move_line, expense_account):
        line = AccountAnalyticLine.objects.create(
            name='linea', company=company, move_line=move_line)
        line.refresh_from_db()
        assert line.general_account_id == expense_account.pk

    def test_an_explicit_general_account_wins_over_the_derived_one(self, company, move_line, expense_account):
        other_account = AccountAccount.objects.create(
            code='60200', name='Otros gastos', account_type='expense', company=company)
        line = AccountAnalyticLine(
            name='linea explicita', company=company, move_line=move_line,
            general_account=other_account)
        line.save()
        line.refresh_from_db()
        assert line.general_account_id == other_account.pk
        assert line.general_account_id != expense_account.pk

    def test_without_a_move_line_general_account_stays_unset(self, company):
        line = AccountAnalyticLine.objects.create(name='sin apunte', company=company)
        line.refresh_from_db()
        assert line.general_account_id is None


class TestCheckGeneralAccountConstraint:
    """≙ ``_check_general_account_id`` (odoo19c: :62-66)."""

    def test_a_mismatched_general_account_raises_on_clean(
        self, company, analytic_account, move_line, expense_account,
    ):
        other_account = AccountAccount.objects.create(
            code='60300', name='Distinta', account_type='expense', company=company)
        line = AccountAnalyticLine(
            name='mal', company=company, account=analytic_account, move_line=move_line,
            general_account=other_account)
        with pytest.raises(ValidationError) as excinfo:
            line.clean()
        assert 'general_account' in excinfo.value.message_dict

    def test_a_matching_general_account_does_not_raise(
        self, company, analytic_account, move_line, expense_account,
    ):
        line = AccountAnalyticLine(
            name='bien', company=company, account=analytic_account, move_line=move_line,
            general_account=expense_account)
        line.clean()

    def test_the_base_constraint_still_applies_without_move_line(self, company):
        """Sin ``move_line`` el mismatch no aplica — pero la validación base
        del mixin (cuenta analítica requerida) sigue corriendo (relevo)."""
        line = AccountAnalyticLine(name='sin cuenta analitica', company=company)
        with pytest.raises(ValidationError) as excinfo:
            line.clean()
        assert 'account' in excinfo.value.message_dict


class TestAnalyticProfitability:
    """≙ ``_compute_analytic_profitability`` (odoo19c: :78-101), sin la
    mitad ``_field_to_sql``/``_search_analytic_profitability`` (divergencia:
    sin framework de ``_search`` custom en este ORM)."""

    def test_an_expense_account_yields_loss(self, company, move_line, expense_account):
        line = AccountAnalyticLine.objects.create(
            name='gasto', company=company, move_line=move_line)
        assert line.analytic_profitability == 'loss'

    def test_an_income_account_yields_revenue(self, company, journal):
        income_account = AccountAccount.objects.create(
            code='70100', name='Ventas', account_type='income', company=company)
        move = AccountMove.objects.create(
            company=company, date=datetime.date.today(), journal=journal)
        income_move_line = AccountMoveLine.objects.create(
            move=move, account=income_account, credit=Decimal('50.00'))
        line = AccountAnalyticLine.objects.create(
            name='ingreso', company=company, move_line=income_move_line)
        assert line.analytic_profitability == 'revenue'

    def test_without_a_move_line_nor_account_type_uncategorized_by_default(self, company):
        line = AccountAnalyticLine.objects.create(
            name='sin cuenta', company=company, category='other', amount=Decimal('0.00'))
        assert line.analytic_profitability == 'uncategorized'

    def test_it_is_not_cached_across_reads(self, company, move_line, expense_account):
        """``store=False`` recalcula en cada lectura."""
        line = AccountAnalyticLine.objects.create(
            name='recalculo', company=company, move_line=move_line)
        assert line.analytic_profitability == 'loss'
        income_account = AccountAccount.objects.create(
            code='70200', name='Ventas 2', account_type='income', company=company)
        line.general_account = income_account
        assert line.analytic_profitability == 'revenue'


class TestProductCodeRefFields:
    def test_product_can_be_set_and_read_back(self, company):
        template = ProductTemplate.objects.create(name='Servicio', company=company)
        product = ProductProduct.objects.create(product_tmpl=template)
        line = AccountAnalyticLine.objects.create(
            name='con producto', company=company, product=product)
        line.refresh_from_db()
        assert line.product_id == product.pk

    def test_code_and_ref_can_be_set_and_read_back(self, company):
        line = AccountAnalyticLine.objects.create(
            name='con code y ref', company=company, code='PRJ0001', ref='REF-1')
        line.refresh_from_db()
        assert line.code == 'PRJ0001'
        assert line.ref == 'REF-1'


class TestWhatStaysBlockedBySecondOrderCause:
    """El conector desbloqueó parte del archivo — no todo. Ver docstring de
    ``account_analytic_line.py``."""

    def test_analytic_line_has_no_journal_field(self):
        """``journal`` (``related='move_line_id.journal_id'``) sigue
        BLOQUEADO: ``account.move.line`` no declara ``journal``."""
        names = {f.name for f in AccountAnalyticLine._meta.get_fields()}
        assert 'journal' not in names

    def test_account_move_line_now_declares_partner_and_journal(self):
        """El bloqueo de segundo orden CAMBIÓ DE DUEÑO — tarea #989.

        Este caso afirmaba lo contrario, y era correcto al escribirse: el
        apunte no declaraba ``partner`` ni ``journal``, así que la línea
        analítica quedaba bloqueada por ellos. Las dos columnas se portaron
        con las otras doce que la vista ``account.invoice.report`` lee.

        Lo que sigue bloqueando a ``journal`` de la línea analítica ya no es
        el apunte: es que el ``related`` de la fuente no se ha tendido. El
        caso hermano de arriba lo mide, y su sucesor sigue siendo el mismo.

        Los dos símbolos llevan el sufijo de la referencia porque ADR-029
        gobierna la forma C: ``partner_id``/``journal_id`` con ``db_column``
        del mismo nombre, no ``partner``/``journal``.
        """
        names = {f.name for f in AccountMoveLine._meta.get_fields()}
        assert 'partner_id' in names
        assert 'journal_id' in names

    def test_the_analytic_distribution_consumer_is_no_longer_blocked(self, company, move_line):
        """Reescrito, no ajustado: antes exigía la ausencia del campo.

        ``create``/``write``/``unlink`` de la fuente actualizan el reparto
        analítico del apunte. Su bloqueo era que el campo no existía; desde la
        tarea #526 existe, y llega por herencia de ``analytic.mixin``.

        Lo que este caso NO afirma es que los tres métodos estén portados: mide
        que su bloqueador cayó, que es un hecho distinto. El porte de los tres
        es la tarea #992.
        """
        names = {f.name for f in AccountMoveLine._meta.get_fields()}
        assert 'analytic_distribution' in names
        assert move_line.analytic_distribution in (None, {})
