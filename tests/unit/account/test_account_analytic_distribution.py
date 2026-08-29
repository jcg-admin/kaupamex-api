"""``account.move.line`` hereda ``analytic.mixin`` — tarea #526.

Tres cosas distintas, separadas a proposito porque fallan por causas
distintas:

1. que la columna y su indice GIN existan;
2. que la **busqueda por cuenta analitica sobre el JSON** encuentre lo que
   debe y descarte lo que no -- es el mecanismo que la referencia construye
   con ``regexp_split_to_array`` + ``&&``, y sin el los dos conteos de
   ``account_analytic_account.py`` no se pueden portar;
3. que los dos conteos devuelvan el numero correcto.

*Metrica:* filas que el predicado de solapamiento devuelve contra PostgreSQL
real, con distribuciones sembradas a mano.
*Ciega a:* el plan de ejecucion -- que el indice GIN se **use** no lo mide
ningun caso de aqui; su presencia si (``TestTheIndexExists``). Medirlo
exigiria un ``EXPLAIN`` sobre un volumen que estos casos no crean.
"""
import datetime
from decimal import Decimal

import pytest
from django.db import connection

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_analytic_account import (
    apply_account_extensions, move_lines_for,
)
from addons.account.models.account_journal import AccountJournal
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.analytic.models import AccountAnalyticAccount, AccountAnalyticPlan
from addons.base.models import ResCompany

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def apply_extension():
    apply_account_extensions()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)


@pytest.fixture
def expense_account(company):
    return AccountAccount.objects.create(
        code='60100', name='Compras', account_type='expense', company=company)


@pytest.fixture
def plan():
    return AccountAnalyticPlan.objects.create(name='Plan')


@pytest.fixture
def cost_center(plan):
    return AccountAnalyticAccount.objects.create(name='Centro A', plan=plan)


@pytest.fixture
def other_center(plan):
    return AccountAnalyticAccount.objects.create(name='Centro B', plan=plan)


def make_line(company, journal, account, move_type, state, distribution):
    move = AccountMove.objects.create(
        company=company, journal=journal, date=datetime.date.today(),
        move_type=move_type, state=state)
    return AccountMoveLine.objects.create(
        move=move, account=account, debit=Decimal('100.00'),
        analytic_distribution=distribution)


class TestTheColumnLanded:

    def test_the_line_declares_analytic_distribution(self):
        names = {f.name for f in AccountMoveLine._meta.get_fields()}
        assert 'analytic_distribution' in names

    def test_the_line_inherits_the_mixin_the_source_names(self):
        """≙ ``_inherit = ["analytic.mixin"]`` (``odoo19c: :21``)."""
        assert AccountMoveLine._inherit == ['analytic.mixin']
        assert 'AnalyticMixin' in [c.__name__ for c in AccountMoveLine.__mro__]

    def test_the_six_class_attributes_the_source_declares(self):
        """La cabecera entera, no dos de seis (``atributos-de-clase-de-modelo``)."""
        assert AccountMoveLine._name == 'account.move.line'
        assert AccountMoveLine._description == 'Journal Item'
        assert AccountMoveLine._order == 'date desc, move_name desc, id'
        assert AccountMoveLine._check_company_auto is True
        assert AccountMoveLine._rec_names_search == ['name', 'move_id', 'product_id']


class TestTheIndexExists:
    """≙ ``init()`` del mixin (``odoo19c: analytic_mixin.py:32-40``)."""

    def test_the_gin_index_is_on_the_table(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexdef FROM pg_indexes WHERE tablename = %s "
                "AND indexname = %s",
                ['account_move_line',
                 'account_move_line_analytic_distribution_accounts_gin_index'])
            row = cursor.fetchone()
        assert row is not None, 'el indice GIN de la migracion 0024 no existe'
        assert 'gin' in row[0].lower()
        assert 'regexp_split_to_array' in row[0]


class TestTheSearchOverTheJson:
    """El predicado que la fuente construye con ``&&`` (``:112-123``)."""

    def test_it_finds_the_line_whose_distribution_names_the_account(
        self, company, journal, expense_account, cost_center,
    ):
        line = make_line(company, journal, expense_account, 'out_invoice',
                         'posted', {str(cost_center.pk): 100.0})
        found = AccountMoveLine.objects.filter(
            AccountMoveLine._search_analytic_distribution('in', [cost_center.pk]))
        assert list(found) == [line]

    def test_it_finds_the_line_whose_key_is_composite(
        self, company, journal, expense_account, cost_center, other_center,
    ):
        """La clave compuesta ``"3,7"`` -- por eso la fuente parte por ``\\D+``."""
        key = f'{cost_center.pk},{other_center.pk}'
        line = make_line(company, journal, expense_account, 'out_invoice',
                         'posted', {key: 100.0})
        for account in (cost_center, other_center):
            found = AccountMoveLine.objects.filter(
                AccountMoveLine._search_analytic_distribution('in', [account.pk]))
            assert list(found) == [line], f'no encontro por {account.name}'

    def test_it_does_not_find_a_line_of_another_account(
        self, company, journal, expense_account, cost_center, other_center,
    ):
        make_line(company, journal, expense_account, 'out_invoice', 'posted',
                  {str(other_center.pk): 100.0})
        found = AccountMoveLine.objects.filter(
            AccountMoveLine._search_analytic_distribution('in', [cost_center.pk]))
        assert list(found) == []

    def test_a_prefix_of_an_id_is_not_a_match(
        self, company, journal, expense_account, plan,
    ):
        """El solapamiento compara elementos del arreglo, no subcadenas.

        Si el predicado usara ``LIKE`` sobre el texto del JSON, la cuenta 1
        casaria con la 12. Este caso cae bajo esa implementacion y pasa bajo
        la de la fuente.
        """
        one = AccountAnalyticAccount.objects.create(name='Uno', plan=plan)
        # La clave se CONSTRUYE para que la contencion este garantizada:
        # ``f'{pk}{pk}'`` contiene el id buscado como subcadena y, como
        # ELEMENTO del arreglo, es un numero distinto. Dejarla al azar de los
        # PK que asigna la secuencia era el defecto: con 41 y 42 no hay
        # contencion, y el caso pasaba tambien bajo la implementacion
        # equivocada (H-API-908).
        superstring = f'{one.pk}{one.pk}'
        assert str(one.pk) in superstring and superstring != str(one.pk)
        make_line(company, journal, expense_account, 'out_invoice', 'posted',
                  {superstring: 100.0})
        found = AccountMoveLine.objects.filter(
            AccountMoveLine._search_analytic_distribution('in', [one.pk]))
        assert list(found) == []

    def test_the_negative_operator_includes_the_null_distribution(
        self, company, journal, expense_account, cost_center,
    ):
        """≙ ``(NOT ... OR ... IS NULL)`` (``:118-123``).

        Un apunte sin distribucion NO solapa, pero ``NULL && ...`` es nulo, no
        falso: sin la rama del ``IS NULL`` desapareceria del resultado.
        """
        without_distribution = make_line(company, journal, expense_account,
                                     'out_invoice', 'posted', None)
        make_line(company, journal, expense_account, 'out_invoice', 'posted',
                  {str(cost_center.pk): 100.0})
        found = AccountMoveLine.objects.filter(
            AccountMoveLine._search_analytic_distribution('not in', [cost_center.pk]))
        assert list(found) == [without_distribution]

    def test_it_resolves_an_account_given_by_name(
        self, company, journal, expense_account, cost_center,
    ):
        """≙ ``search_value(v, exact=True)`` (``:87-90``)."""
        line = make_line(company, journal, expense_account, 'out_invoice',
                         'posted', {str(cost_center.pk): 100.0})
        found = AccountMoveLine.objects.filter(
            AccountMoveLine._search_analytic_distribution('in', ['Centro A']))
        assert list(found) == [line]

    def test_ilike_collapses_to_in_and_matches_partially(
        self, company, journal, expense_account, cost_center,
    ):
        """≙ la rama ``ilike`` (``:100-103``), que colapsa a ``in``."""
        line = make_line(company, journal, expense_account, 'out_invoice',
                         'posted', {str(cost_center.pk): 100.0})
        found = AccountMoveLine.objects.filter(
            AccountMoveLine._search_analytic_distribution('ilike', 'entro A'))
        assert list(found) == [line]

    def test_an_unknown_name_yields_nothing_and_does_not_raise(
        self, company, journal, expense_account, cost_center,
    ):
        """≙ ``return Domain(operator == 'not in')`` (``:110-112``)."""
        make_line(company, journal, expense_account, 'out_invoice', 'posted',
                  {str(cost_center.pk): 100.0})
        found = AccountMoveLine.objects.filter(
            AccountMoveLine._search_analytic_distribution('in', ['no existe']))
        assert list(found) == []

    def test_an_unsupported_operator_raises_naming_it(self):
        """≙ ``raise UserError(_('Operation not supported'))`` (``:105``)."""
        with pytest.raises(ValueError) as exc:
            AccountMoveLine._search_analytic_distribution('>', [1])
        assert 'OPERATOR_NOT_SUPPORTED' in str(exc.value)


class TestTheCounts:
    """≙ ``_compute_invoice_count`` / ``_compute_vendor_bill_count``."""

    def test_a_customer_invoice_counts_as_invoice_and_not_as_bill(
        self, company, journal, expense_account, cost_center,
    ):
        make_line(company, journal, expense_account, 'out_invoice', 'posted',
                  {str(cost_center.pk): 100.0})
        assert cost_center.invoice_count == 1
        assert cost_center.vendor_bill_count == 0

    def test_a_vendor_bill_counts_as_bill_and_not_as_invoice(
        self, company, journal, expense_account, cost_center,
    ):
        make_line(company, journal, expense_account, 'in_invoice', 'posted',
                  {str(cost_center.pk): 100.0})
        assert cost_center.vendor_bill_count == 1
        assert cost_center.invoice_count == 0

    def test_a_receipt_counts_because_the_source_includes_them(
        self, company, journal, expense_account, cost_center,
    ):
        """≙ ``get_sale_types(include_receipts=True)`` (``:20``)."""
        make_line(company, journal, expense_account, 'out_receipt', 'posted',
                  {str(cost_center.pk): 100.0})
        assert cost_center.invoice_count == 1

    def test_a_draft_move_does_not_count(
        self, company, journal, expense_account, cost_center,
    ):
        """≙ ``('parent_state', '=', 'posted')`` (``:23``)."""
        make_line(company, journal, expense_account, 'out_invoice', 'draft',
                  {str(cost_center.pk): 100.0})
        assert cost_center.invoice_count == 0

    def test_an_entry_counts_in_neither(
        self, company, journal, expense_account, cost_center,
    ):
        make_line(company, journal, expense_account, 'entry', 'posted',
                  {str(cost_center.pk): 100.0})
        assert cost_center.invoice_count == 0
        assert cost_center.vendor_bill_count == 0

    def test_two_lines_of_the_same_account_both_count(
        self, company, journal, expense_account, cost_center,
    ):
        for _ in range(2):
            make_line(company, journal, expense_account, 'out_invoice',
                      'posted', {str(cost_center.pk): 100.0})
        assert cost_center.invoice_count == 2

    def test_move_lines_for_returns_nothing_without_accounts(self):
        assert list(move_lines_for([], ['out_invoice'])) == []
