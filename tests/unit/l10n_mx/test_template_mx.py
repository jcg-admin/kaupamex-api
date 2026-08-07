"""El plan contable mexicano y lo que le escribe a la empresa.

Portación de ``odoo19c: l10n_mx/models/template_mx.py`` (addon ``l10n_mx``,
LGPL-3, ``odoo-tools@622ddc2a``).

Cubre el quinto método —el override de ``_get_accounts_data_values``— que hasta
este pase estaba declarado bloqueado por falta de un punto de extensión. Ver
:ref:`h-api-360`.
"""
import pytest

from addons.account.models.chart_template import (
    ACCOUNTS_DATA_OVERRIDES,
    TEMPLATE_REGISTRY,
    ChartTemplate,
)
from addons.base.models import ResCompany, ResCountry

pytestmark = pytest.mark.django_db


@pytest.fixture
def mexican_company():
    return ResCompany.objects.create(
        code='mx-co', name='Empresa MX',
        account_fiscal_country=ResCountry.objects.get(code='MX'),
    )


@pytest.fixture
def foreign_company():
    return ResCompany.objects.create(
        code='es-co', name='Empresa ES',
        account_fiscal_country=ResCountry.objects.get(code='ES'),
    )


class TestAccountsDataOverride:
    """El punto de extensión que la referencia resuelve con ``_inherit``."""

    def test_the_mx_override_is_registered(self):
        """Importar ``template_mx`` basta — el decorador registra al importar."""
        nombres = {f.__name__ for f in ACCOUNTS_DATA_OVERRIDES}
        assert 'add_mx_cash_difference_accounts' in nombres

    def test_a_mexican_company_gets_the_sat_literal_codes(
            self, mexican_company):
        """``403.01.01`` y ``601.84.02`` — ≙ ``odoo19c: template_mx.py:67-76``.

        La genérica declara estas dos por ``prefix``; el catálogo del SAT las
        fija por código, así que la entrada se reemplaza entera.
        """
        datos = ChartTemplate.get_accounts_data_values(
            mexican_company, {'code_digits': 6})

        assert datos['default_cash_difference_income_account']['code'] == '403.01.01'
        assert datos['default_cash_difference_expense_account']['code'] == '601.84.02'

    def test_a_foreign_company_keeps_the_generic_accounts(
            self, foreign_company):
        """La guarda vive en el método, no en el cableado.

        Es lo que hace la referencia: el ``_inherit`` se instala para toda
        carga y filtra por ``company.account_fiscal_country_id.code == 'MX'``.
        """
        datos = ChartTemplate.get_accounts_data_values(
            foreign_company, {'code_digits': 6})

        assert 'code' not in datos['default_cash_difference_income_account']
        assert datos['default_cash_difference_income_account']['prefix'] == '999'

    def test_a_company_without_fiscal_country_keeps_the_generic_accounts(self):
        """Sin país fiscal no hay override — y no revienta al preguntarlo."""
        company = ResCompany.objects.create(code='sin-pais-mx', name='Sin país')
        datos = ChartTemplate.get_accounts_data_values(
            company, {'code_digits': 6})

        assert datos['default_cash_difference_expense_account']['prefix'] == '999'

    def test_the_override_does_not_touch_the_other_four_accounts(
            self, mexican_company):
        """Reemplaza dos entradas, no el dict — las otras cuatro siguen."""
        datos = ChartTemplate.get_accounts_data_values(
            mexican_company, {'code_digits': 6})

        assert set(datos) == {
            'account_journal_suspense_account',
            'account_journal_early_pay_discount_loss_account',
            'account_journal_early_pay_discount_gain_account',
            'default_cash_difference_income_account',
            'default_cash_difference_expense_account',
            'transfer_account',
        }


class TestMxResCompany:
    """Lo que el plan escribe en la empresa — ≙ ``_get_mx_res_company``."""

    def test_the_chart_declares_mexico_as_the_fiscal_country(self):
        """La décima clave con campo donde aterrizar (:ref:`h-api-360`).

        No es cosmética: de ella depende que el override de las cuentas de
        diferencia de efectivo reconozca a la empresa como mexicana.

        Se lee del registro y no de ``get_chart_template_data`` porque
        ``res.company`` no es un modelo instanciado desde CSV: sus valores los
        consume ``post_load_data`` (``chart_template.py:807``), igual que en la
        referencia, donde ``_post_load_data`` los escribe sobre la empresa ya
        creada.
        """
        valores = {}
        for func in TEMPLATE_REGISTRY['mx']['res.company']:
            valores.update(func(ChartTemplate, 'mx'))

        assert valores['account_fiscal_country'] == 'base.mx'
