"""``account`` sobre ``account.analytic.distribution.model`` (tarea #398, T2).

Único símbolo portado: ``prefix_placeholder`` (``store=False``) — ver el
docstring de ``account_analytic_distribution_model.py``. ``_get_
default_search_domain_vals``/``_get_applicable_models``/``_create_domain``
quedan BLOQUEADOS (necesitan ``account_prefix``/``product_id``/
``product_categ_id``, migración fuera del alcance de este tramo) y se
verifican como tal, igual que en los archivos hermanos de este tramo.
"""
import pytest

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_analytic_distribution_model import (
    apply_account_analytic_distribution_model_extensions,
)
from addons.analytic.models import AccountAnalyticDistributionModel
from addons.base.models import ResCompany

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def apply_extension():
    """Idempotente (``_add_if_absent``) — segura de invocar en cada test aunque
    otro módulo ya la haya aplicado en el mismo proceso."""
    apply_account_analytic_distribution_model_extensions()


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


class TestPrefixPlaceholder:
    """≙ ``_compute_prefix_placeholder`` (odoo19c: :53-70)."""

    def test_without_an_expense_account_uses_the_60_61_62_default(self, company):
        record = AccountAnalyticDistributionModel.objects.create(company=company)
        assert record.prefix_placeholder == 'e.g. 60, 61, 62'

    def test_with_an_expense_account_derives_the_prefix_from_its_code(self, company):
        AccountAccount.objects.create(
            code='601', name='Compras', account_type='expense', company=company)
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

    def test_it_is_not_cached_across_reads(self, company):
        """``store=False`` recalcula en cada lectura — a diferencia de un
        campo almacenado, cambiar el estado subyacente cambia el valor sin
        volver a guardar el registro."""
        record = AccountAnalyticDistributionModel.objects.create(company=company)
        assert record.prefix_placeholder == 'e.g. 60, 61, 62'
        AccountAccount.objects.create(
            code='701', name='Ingresos', account_type='expense', company=company)
        assert record.prefix_placeholder == 'e.g. 70, 71, 72'


class TestTheThreeBlockedMethods:
    def test_the_model_has_no_account_prefix_nor_product_fields(self):
        names = {f.name for f in AccountAnalyticDistributionModel._meta.get_fields()}
        assert 'account_prefix' not in names
        assert 'product' not in names
        assert 'product_categ' not in names

    def test_get_applicable_models_from_the_base_stays_unwrapped(self):
        """No se envolvió — la base sigue resolviendo sola, sin la rama de
        ``account_prefix`` que la referencia añade."""
        result = AccountAnalyticDistributionModel._get_applicable_models({})
        assert list(result) == []
