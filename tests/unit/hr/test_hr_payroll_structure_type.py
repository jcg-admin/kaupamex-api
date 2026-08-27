"""``hr.payroll.structure.type`` — tipo de estructura salarial (addon ``hr``).

Adaptación fiel de Odoo hr/models/hr_payroll_structure_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import pytest

from addons.base.models import ResCompany, ResCountry
from addons.hr.models import HrPayrollStructureType
from orm.environments import set_current_company

pytestmark = pytest.mark.django_db


@pytest.fixture
def mexico():
    return ResCountry.objects.get(code='MX')


@pytest.fixture
def company(mexico):
    company = ResCompany.objects.create(code='hr-payroll', name='HR Payroll')
    company.partner.country = mexico
    company.partner.save(update_fields=['country'])
    return company


class TestHrPayrollStructureTypeDefaultCountry:
    """≙ ``default=lambda self: self.env.company.country_id``."""

    def test_default_country_is_the_active_company_country(self, company):
        set_current_company(company.pk)
        try:
            structure_type = HrPayrollStructureType.objects.create()
        finally:
            set_current_company(None)
        assert structure_type.country_id == company.partner.country_id

    def test_without_an_active_company_country_stays_empty(self):
        set_current_company(None)
        structure_type = HrPayrollStructureType.objects.create()
        assert structure_type.country_id is None


class TestHrPayrollStructureTypeCountryCode:
    """≙ ``related='country_id.code'``, expuesto como ``@property``."""

    def test_country_code_reads_through_country(self, mexico):
        structure_type = HrPayrollStructureType.objects.create(country=mexico)
        assert structure_type.country_code == mexico.code

    def test_country_code_is_empty_without_a_country(self):
        structure_type = HrPayrollStructureType.objects.create()
        assert structure_type.country_code == ''


class TestHrPayrollStructureTypeStr:

    def test_str_returns_name(self):
        structure_type = HrPayrollStructureType.objects.create(
            name='Nómina mensual')
        assert str(structure_type) == 'Nómina mensual'
