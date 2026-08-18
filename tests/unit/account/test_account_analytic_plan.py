"""``account`` sobre ``account.analytic.applicability`` (tarea #398, tramo 2).

Pese a su nombre, el archivo de la referencia extiende ``account.analytic.
applicability`` (medido por AST al abrir este tramo), no ``account.analytic.
plan`` — ver docstring de ``account_analytic_plan.py``. Se portan 3 de los 5
símbolos: la ampliación de ``business_domain`` (``invoice``/``bill``) y los
dos campos ``store=False`` que dependen de ella. ``account_prefix``/
``product_categ_id``/``_get_score`` quedan BLOQUEADOS (migración fuera de
alcance) y se verifican como tal.
"""
import pytest

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_analytic_plan import (
    apply_account_analytic_plan_extensions,
)
from addons.analytic.models import AccountAnalyticApplicability
from addons.base.models import ResCompany

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def apply_extension():
    apply_account_analytic_plan_extensions()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


class TestBusinessDomainExtended:
    """≙ ``selection_add=[('invoice', ...), ('bill', ...)]`` (odoo19c: :12-18)."""

    def test_invoice_and_bill_are_in_the_choices(self):
        field = AccountAnalyticApplicability._meta.get_field('business_domain')
        values = {value for value, _ in field.choices}
        assert {'invoice', 'bill'} <= values

    def test_general_from_the_base_is_still_present(self):
        """Ampliar no reemplaza — el valor de la base convive con los nuevos."""
        field = AccountAnalyticApplicability._meta.get_field('business_domain')
        values = {value for value, _ in field.choices}
        assert 'general' in values

    def test_it_is_idempotent(self):
        """Aplicar dos veces no duplica la entrada (``ready()`` puede correr
        más de una vez en tests que recargan el registro)."""
        apply_account_analytic_plan_extensions()
        apply_account_analytic_plan_extensions()
        field = AccountAnalyticApplicability._meta.get_field('business_domain')
        values = [value for value, _ in field.choices]
        assert values.count('invoice') == 1
        assert values.count('bill') == 1

    def test_a_record_with_the_new_value_can_be_saved(self, company):
        """La prueba que importa: no sólo está en ``choices``, se persiste."""
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='invoice', applicability='optional', company=company)
        applicability.refresh_from_db()
        assert applicability.business_domain == 'invoice'


class TestDisplayAccountPrefix:
    """≙ ``_compute_display_account_prefix`` (odoo19c: :78-81)."""

    @pytest.mark.parametrize('domain,expected', [
        ('general', True),
        ('invoice', True),
        ('bill', True),
    ])
    def test_it_shows_for_general_invoice_and_bill(self, company, domain, expected):
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain=domain, applicability='optional', company=company)
        assert applicability.display_account_prefix is expected

    def test_it_creates_no_column(self):
        """``store=False`` (``NonStored``) no aparece en ``_meta`` — se
        comprueba como el atributo de clase que realmente es, no como una
        columna ausente por casualidad."""
        assert hasattr(AccountAnalyticApplicability, 'display_account_prefix')
        columns = {f.column for f in AccountAnalyticApplicability._meta.fields}
        assert 'display_account_prefix' not in columns


class TestAccountPrefixPlaceholder:
    """≙ ``_compute_prefix_placeholder`` (odoo19c: :34-57) — SIN filtro de
    compañía, a diferencia del homónimo de ``account_analytic_distribution_
    model.py`` (la referencia tampoco lo filtra aquí)."""

    def test_bill_uses_the_expense_account_and_prefix_60(self, company):
        AccountAccount.objects.create(
            code='601', name='Compras', account_type='expense', company=company)
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='bill', applicability='optional', company=company)
        assert applicability.account_prefix_placeholder == 'e.g. 60, 61, 62'

    def test_invoice_uses_the_income_account_and_prefix_40(self, company):
        AccountAccount.objects.create(
            code='401', name='Ventas', account_type='income', company=company)
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='invoice', applicability='optional', company=company)
        assert applicability.account_prefix_placeholder == 'e.g. 40, 41, 42'

    def test_general_falls_into_the_income_branch_like_the_reference(self, company):
        """``if business_domain == 'bill': ... else: ...`` — cualquier otro
        valor (incluido ``general``) toma la rama de ingreso, tal cual la
        referencia lo escribe."""
        AccountAccount.objects.create(
            code='401', name='Ventas', account_type='income', company=company)
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company)
        assert applicability.account_prefix_placeholder == 'e.g. 40, 41, 42'

    def test_without_an_account_it_uses_the_reference_default(self, company):
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='bill', applicability='optional', company=company)
        assert applicability.account_prefix_placeholder == 'e.g. 60, 61, 62'

    def test_it_ignores_the_records_company_like_the_reference(self, company):
        """A diferencia de ``account_analytic_distribution_model.py``, aquí
        la referencia NO filtra por compañía — se porta tal cual."""
        other_company = ResCompany.objects.create(code='otra', name='Otra SA')
        AccountAccount.objects.create(
            code='601', name='Compras', account_type='expense',
            company=other_company)
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='bill', applicability='optional', company=company)
        assert applicability.account_prefix_placeholder == 'e.g. 60, 61, 62'


class TestWhatStaysBlocked:
    def test_the_model_has_no_account_prefix_nor_product_categ_fields(self):
        names = {f.name for f in AccountAnalyticApplicability._meta.get_fields()}
        assert 'account_prefix' not in names
        assert 'product_categ' not in names

    def test_get_score_from_the_base_stays_unwrapped(self, company):
        """``_get_score`` no fue envuelto — su firma y comportamiento son
        exactamente los de ``analytic_plan.py`` (ver ese archivo)."""
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company)
        assert applicability._get_score(company_id=company.pk) == 0.5
