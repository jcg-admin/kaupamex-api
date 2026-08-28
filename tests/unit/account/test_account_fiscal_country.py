"""El país fiscal de la empresa y los ``fiscal_country_codes`` que deriva.

Portación de ``odoo19c: account/models/company.py:203-209,363-403`` y del
mecanismo ``fiscal_country_codes`` que la referencia reparte en diez clases
(``odoo-tools@622ddc2a``, addon ``account``, LGPL-3).

Es la raíz que mantenía bloqueados los dos campos de ``l10n_mx: res_bank.py``
y los cuatro hermanos de ``account`` — ver :ref:`h-api-360`.
"""
import pytest

from addons.account.models.account_fiscal_position import AccountFiscalPosition
from addons.account.models.account_payment_term import AccountPaymentTerm
from addons.account.models.res_company import get_fiscal_country_codes
from addons.base.models import ResBank, ResCompany, ResCountry, ResCurrency
from addons.base.models.res_bank import ResPartnerBank
from orm.environments import set_current_company

pytestmark = pytest.mark.django_db


@pytest.fixture
def mexico():
    return ResCountry.objects.get(code='MX')


@pytest.fixture
def spain():
    return ResCountry.objects.get(code='ES')


@pytest.fixture
def company(mexico):
    return ResCompany.objects.create(code='fiscal-mx', name='Fiscal MX',
                                     account_fiscal_country=mexico)


class TestAccountFiscalCountry:
    """El campo y su resolutor — ≙ ``compute_account_tax_fiscal_country``."""

    def test_the_company_carries_its_fiscal_country(self, company, mexico):
        company.refresh_from_db()
        assert company.account_fiscal_country == mexico

    def test_the_resolver_falls_back_to_the_company_country(self, mexico):
        """≙ ``odoo19c: company.py:387-390``.

        El resolutor sólo rellena cuando nadie fijó el país fiscal; el país de
        la empresa vive en su partner, así que se escribe ahí.
        """
        company = ResCompany.objects.create(code='sin-fiscal', name='Sin país')
        company.partner.country = mexico
        company.partner.save(update_fields=['country'])
        assert company.account_fiscal_country is None
        assert company.compute_account_tax_fiscal_country() == mexico

    def test_the_resolver_does_not_overwrite_an_explicit_value(
            self, company, spain):
        """La referencia lo declara ``readonly=False``: lo puesto persiste."""
        assert company.compute_account_tax_fiscal_country() != spain
        company.account_fiscal_country = spain
        assert company.compute_account_tax_fiscal_country() == spain


class TestFiscalCountryGroupCodes:
    """≙ ``_compute_account_fiscal_country_group_codes``."""

    def test_returns_the_groups_of_its_fiscal_country(self, spain):
        company = ResCompany.objects.create(
            code='fiscal-es', name='Fiscal ES', account_fiscal_country=spain)
        assert 'EU' in company.account_fiscal_country_group_codes

    def test_returns_a_list_with_an_empty_string_when_there_is_none(self):
        """No ``[]`` — la referencia devuelve ``['']`` y eso es contrato."""
        company = ResCompany.objects.create(code='sin-pais', name='Sin país')
        assert company.account_fiscal_country_group_codes == ['']


class TestEnabledTaxCountries:
    """≙ ``_compute_account_enabled_tax_country_ids``."""

    def test_includes_its_own_fiscal_country(self, company, mexico):
        assert mexico in company.get_account_enabled_tax_countries()

    def test_includes_the_countries_of_its_foreign_vat_positions(
            self, company, spain):
        """Una empresa registrada para IVA en otro país usa sus impuestos."""
        AccountFiscalPosition.objects.create(
            company=company, name='IVA España', country=spain,
            foreign_vat='ESX1234567',
        )
        enabled = company.get_account_enabled_tax_countries()
        assert spain in enabled

    def test_a_position_without_foreign_vat_does_not_enable_its_country(
            self, company, spain):
        AccountFiscalPosition.objects.create(
            company=company, name='Sin VAT propio', country=spain,
        )
        assert spain not in company.get_account_enabled_tax_countries()


class TestFiscalCountryCodes:
    """El derivado de sesión que la referencia declara en diez clases."""

    def test_the_helper_reads_the_active_companies(self, company):
        set_current_company(company.pk)
        try:
            assert get_fiscal_country_codes() == 'MX'
        finally:
            set_current_company(None)

    def test_the_helper_preserves_the_order_of_the_companies(
            self, company, spain):
        """``mapped`` respeta el orden del recordset; un ``pk__in`` lo perdería."""
        other = ResCompany.objects.create(
            code='fiscal-es2', name='Fiscal ES2', account_fiscal_country=spain)
        assert get_fiscal_country_codes([company.pk, other.pk]) == 'MX,ES'
        assert get_fiscal_country_codes([other.pk, company.pk]) == 'ES,MX'

    def test_a_company_without_fiscal_country_contributes_nothing(
            self, company):
        empty = ResCompany.objects.create(code='vacia', name='Vacía')
        assert get_fiscal_country_codes([company.pk, empty.pk]) == 'MX'

    @pytest.mark.parametrize('model', [ResBank, ResPartnerBank, ResCurrency])
    def test_the_session_shape_is_hung_on_its_three_models(
            self, model, company):
        """≙ ``res_currency.py`` y las dos clases de ``l10n_mx: res_bank.py``."""
        set_current_company(company.pk)
        try:
            assert model().fiscal_country_codes == 'MX'
        finally:
            set_current_company(None)

    def test_the_record_shape_prefers_the_company_of_the_record(
            self, company, spain):
        """≙ ``product.py``/``account_payment_term.py``: ``record.company_id
        or self.env.companies``."""
        other = ResCompany.objects.create(
            code='fiscal-es3', name='Fiscal ES3', account_fiscal_country=spain)
        term = AccountPaymentTerm.objects.create(name='30 días', company=other)
        set_current_company(company.pk)
        try:
            assert term.fiscal_country_codes == 'ES'
            assert AccountPaymentTerm(company=None).fiscal_country_codes == 'MX'
        finally:
            set_current_company(None)

    def test_the_partner_shape_appends_its_own_country(self, company, spain):
        """≙ ``partner.py:342-349`` — el país del propio partner se suma."""
        set_current_company(company.pk)
        try:
            partner = company.partner
            partner.country = spain
            partner.save(update_fields=['country'])
            codes = partner.fiscal_country_codes.split(',')
            assert 'MX' in codes and 'ES' in codes
        finally:
            set_current_company(None)
