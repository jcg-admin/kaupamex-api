"""``account`` sobre ``account.analytic.applicability`` (tarea #520).

Pese a su nombre, el archivo de la referencia extiende ``account.analytic.
applicability`` (medido por AST), no ``account.analytic.plan`` — ver
docstring de ``account_analytic_plan.py``. Los 3 ``def`` de la referencia
están portados: la ampliación de ``business_domain`` y los dos campos
``store=False`` (tramo anterior), más ``_get_score`` — envuelto vía
``chain_method`` con los 2 campos que ``addons/analytic/migrations/``
desbloqueó en esta tarea (``account_prefix``, ``product_categ``).
"""
import pytest

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_analytic_plan import apply_account_extensions
from addons.analytic.models import AccountAnalyticApplicability
from addons.base.models import ResCompany
from addons.product.models import ProductCategory, ProductProduct, ProductTemplate

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def apply_extension():
    apply_account_extensions()


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
        apply_account_extensions()
        apply_account_extensions()
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


class TestAccountPrefixAndProductCategFields:
    """≙ las 2 columnas nuevas (odoo19c: :20-27), desbloqueadas en tarea
    #520 por ``addons/analytic/migrations/``."""

    def test_the_model_has_real_columns_for_both(self):
        columns = {f.column for f in AccountAnalyticApplicability._meta.fields}
        assert {'account_prefix', 'product_categ_id'} <= columns

    def test_product_categ_can_be_set_and_read_back(self, company):
        categ = ProductCategory.objects.create(name='Servicios')
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company,
            product_categ=categ)
        applicability.refresh_from_db()
        assert applicability.product_categ_id == categ.pk


class TestGetScoreWrappedWithAccountPrefixAndProductCateg:
    """≙ ``_get_score`` (odoo19c: :59-76) — envuelve la base con
    ``chain_method``+``combine``, desbloqueado en tarea #520."""

    def test_without_account_prefix_nor_product_categ_only_the_base_score_applies(self, company):
        """Sin los dos campos nuevos, el comportamiento es idéntico al de la
        base — el envoltorio no aporta ni resta nada."""
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company)
        assert applicability._get_score(company_id=company.pk) == 0.5

    def test_account_prefix_matching_adds_one_point(self, company):
        AccountAccount.objects.create(
            code='601100', name='Compras', account_type='expense', company=company)
        account = AccountAccount.objects.get(code='601100')
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company,
            account_prefix='601, 602')
        assert applicability._get_score(company_id=company.pk, account=account.pk) == 1.5

    def test_account_prefix_not_matching_vetoes_to_minus_one(self, company):
        """El veto descarta INCLUSO el puntaje base ya ganado — mismo
        criterio de corto-circuito que la referencia (odoo19c: :69-72)."""
        AccountAccount.objects.create(
            code='701100', name='Ventas', account_type='income', company=company)
        account = AccountAccount.objects.get(code='701100')
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company,
            account_prefix='601, 602')
        assert applicability._get_score(company_id=company.pk, account=account.pk) == -1

    def test_a_base_score_of_minus_one_short_circuits_before_the_bonus(self, company):
        """``business_domain`` no coincide → base ya es ``-1`` (odoo19c:
        :454-455) — el bonus ni se evalúa."""
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='invoice', applicability='optional', company=company,
            account_prefix='601')
        assert applicability._get_score(business_domain='bill') == -1

    def test_product_categ_matching_adds_one_point(self, company):
        categ = ProductCategory.objects.create(name='Consultoría')
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company,
            product_categ=categ)
        template = ProductTemplate.objects.create(
            name='Hora de consultoría', company=company, categ=categ)
        product = ProductProduct.objects.create(product_tmpl=template)
        assert applicability._get_score(
            company_id=company.pk, product=product.pk) == 1.5

    def test_it_is_idempotent(self, company):
        """``chain_method`` no re-envuelve al reaplicar — mismo puntaje que
        sin reaplicar, no doble bonus."""
        apply_account_extensions()
        apply_account_extensions()
        AccountAccount.objects.create(
            code='601200', name='Compras', account_type='expense', company=company)
        account = AccountAccount.objects.get(code='601200')
        applicability = AccountAnalyticApplicability.objects.create(
            business_domain='general', applicability='optional', company=company,
            account_prefix='601')
        assert applicability._get_score(company_id=company.pk, account=account.pk) == 1.5
