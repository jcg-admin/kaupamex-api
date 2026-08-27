"""``account`` sobre ``account.analytic.distribution.model`` (tarea #520).

Los 4 ``def`` de la referencia están portados: ``prefix_placeholder``
(``store=False``, ya en el tramo anterior) y los 3 que
``addons/analytic/migrations/`` desbloqueó en esta tarea —
``_get_default_search_domain_vals``, ``_create_domain``,
``_get_applicable_models`` — junto con sus 3 campos nuevos
(``account_prefix``, ``product``, ``product_categ``). Ver el docstring de
``account_analytic_distribution_model.py``.
"""
import models
import pytest

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_analytic_distribution_model import (
    apply_account_extensions,
)
from addons.analytic.models import AccountAnalyticDistributionModel
from addons.base.models import ResCompany
from addons.product.models import ProductCategory, ProductProduct, ProductTemplate

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def apply_extension():
    """Idempotente (``_add_if_absent`` / ``chain_method``) — segura de
    invocar en cada test aunque otro módulo ya la haya aplicado en el mismo
    proceso."""
    apply_account_extensions()


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


class TestTheFieldWasApplied:
    def test_prefix_placeholder_exists_on_the_model(self):
        """``store=False`` (``NonStored``) NO aparece en ``_meta.get_fields()``
        — eso es justamente lo que "sin columna" significa. Se comprueba
        como el atributo de clase que realmente es."""
        assert hasattr(AccountAnalyticDistributionModel, 'prefix_placeholder')

    def test_prefix_placeholder_creates_no_column(self):
        names_in_meta = {f.name for f in AccountAnalyticDistributionModel._meta.get_fields()}
        columns = {f.column for f in AccountAnalyticDistributionModel._meta.fields}
        assert 'prefix_placeholder' not in names_in_meta
        assert 'prefix_placeholder' not in columns

    def test_account_prefix_product_and_product_categ_exist_as_real_columns(self):
        """A diferencia de ``prefix_placeholder``, estos SÍ son columnas
        reales (``store=True`` implícito — la referencia no declara
        ``store=False`` para ninguno de los tres)."""
        columns = {f.column for f in AccountAnalyticDistributionModel._meta.fields}
        assert {'account_prefix', 'product_id', 'product_categ_id'} <= columns


class TestPrefixPlaceholder:
    """≙ ``_compute_prefix_placeholder`` (odoo19c: :53-70)."""

    def test_without_an_expense_account_uses_the_60_61_62_default(self, company):
        record = AccountAnalyticDistributionModel.objects.create(company=company)
        assert record.prefix_placeholder == 'e.g. 60, 61, 62'

    def test_derives_from_the_real_code_not_the_default(self, company):
        """El prefijo sale de la cuenta encontrada, no de la constante — si
        el código empezara en 55 debe verse 55/56/57, no 60/61/62."""
        AccountAccount.objects.create(
            code='550100', name='Servicios', account_type='expense',
            company=company)
        record = AccountAnalyticDistributionModel.objects.create(company=company)
        assert record.prefix_placeholder == 'e.g. 55, 56, 57'

    def test_without_a_company_it_does_not_filter_by_company(self, company):
        """``self.env.company`` (compañía activa) no existe aquí — se
        sustituye por ``self.company``; sin ella, la búsqueda queda sin
        filtrar (ver docstring del módulo)."""
        AccountAccount.objects.create(
            code='601', name='Compras', account_type='expense', company=company)
        record = AccountAnalyticDistributionModel.objects.create(company=None)
        assert record.prefix_placeholder == 'e.g. 60, 61, 62'


class TestDefaultSearchDomainVals:
    """≙ ``_get_default_search_domain_vals`` (odoo19c: :78-84) —
    ``combine`` fusiona el dict base con ``product``/``product_categ``."""

    def test_includes_the_base_keys_and_the_two_new_ones(self):
        vals = AccountAnalyticDistributionModel._get_default_search_domain_vals()
        assert vals == {
            'company_id': None, 'partner_id': None,
            'product': None, 'product_categ': None,
        }


class TestCreateDomainAccountPrefix:
    """≙ la rama nueva de ``_create_domain`` (odoo19c: :86-89) — no filtra
    por igualdad, devuelve un dominio vacío (matches todo)."""

    def test_account_prefix_returns_an_always_true_q(self):
        domain = AccountAnalyticDistributionModel._create_domain('account_prefix', 'x')
        assert domain == models.Q()

    def test_other_fields_still_relay_to_the_base_isnull_check(self):
        domain = AccountAnalyticDistributionModel._create_domain('company_id', None)
        assert domain == models.Q(company_id__isnull=True)


class TestGetApplicableModelsFiltersByAccountPrefix:
    """≙ ``_get_applicable_models`` (odoo19c: :94-99)."""

    def test_a_model_without_prefix_always_matches(self, company):
        without_prefix = AccountAnalyticDistributionModel.objects.create(company=company)
        result = AccountAnalyticDistributionModel._get_applicable_models(
            {'company_id': company.pk, 'account_prefix': '999999'})
        assert without_prefix.pk in {m.pk for m in result}

    def test_a_model_with_a_matching_prefix_is_included(self, company):
        with_prefix = AccountAnalyticDistributionModel.objects.create(
            company=company, account_prefix='601, 602')
        result = AccountAnalyticDistributionModel._get_applicable_models(
            {'company_id': company.pk, 'account_prefix': '601500'})
        assert with_prefix.pk in {m.pk for m in result}

    def test_a_model_with_a_non_matching_prefix_is_excluded(self, company):
        with_prefix = AccountAnalyticDistributionModel.objects.create(
            company=company, account_prefix='601, 602')
        result = AccountAnalyticDistributionModel._get_applicable_models(
            {'company_id': company.pk, 'account_prefix': '999999'})
        assert with_prefix.pk not in {m.pk for m in result}

    def test_the_delimiter_splits_on_comma_or_semicolon(self, company):
        with_prefix = AccountAnalyticDistributionModel.objects.create(
            company=company, account_prefix='601;602')
        result = AccountAnalyticDistributionModel._get_applicable_models(
            {'company_id': company.pk, 'account_prefix': '602100'})
        assert with_prefix.pk in {m.pk for m in result}


class TestProductAndProductCategFields:
    def test_product_can_be_set_and_read_back(self, company):
        template = ProductTemplate.objects.create(name='Widget', company=company)
        product = ProductProduct.objects.create(product_tmpl=template)
        record = AccountAnalyticDistributionModel.objects.create(
            company=company, product=product)
        record.refresh_from_db()
        assert record.product_id == product.pk

    def test_product_categ_can_be_set_and_read_back(self, company):
        categ = ProductCategory.objects.create(name='Servicios')
        record = AccountAnalyticDistributionModel.objects.create(
            company=company, product_categ=categ)
        record.refresh_from_db()
        assert record.product_categ_id == categ.pk
