"""``hr.employee`` — la delegación a ``hr.version`` (addon ``hr``, tarea #513).

Adaptación de Odoo hr/models/hr_employee.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3). Este archivo cubre SOLO las 24 propiedades de delegación que la
tarea #513 conectó contra ``self.version`` (ver el hallazgo :ref:`h-api-690`
y el docstring de ``hr_employee.py`` — sección "Delegación a hr.version").
La cobertura del resto del modelo (identidad, avatar, bancario, etc.) es
deuda pre-existente de H-API-683, fuera de este alcance.
"""
from datetime import date
from decimal import Decimal

import pytest

from addons.hr.models import HrDepartment, HrEmployee, HrVersion

pytestmark = pytest.mark.django_db


class TestHrEmployeeVersionDelegationWithoutAVersion:
    """Sin ``version`` asignada, cada propiedad devuelve el vacío de su tipo
    — nunca levanta (mismo criterio que las propiedades de ``resource.user``
    ya existentes en este archivo)."""

    def test_current_version_is_none(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.current_version is None

    def test_current_date_version_is_none(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.current_date_version is None

    def test_versions_count_is_zero(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.versions_count == 0

    def test_version_revision_is_zero(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.version_revision == 0

    def test_contract_wage_is_zero_decimal(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.contract_wage == Decimal('0.00')

    def test_is_current_is_false(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.is_current is False

    def test_department_is_none(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.department is None

    def test_job_title_is_empty_string(self):
        employee = HrEmployee.objects.create(name='Sin versión')
        assert employee.job_title == ''


class TestHrEmployeeVersionDelegationWithAVersion:
    """Con ``version`` asignada, cada propiedad lee a través de ella —
    ≙ los campos ``related='version_id.*', inherited=True`` de la referencia."""

    def _employee_with_version(self, **version_kwargs):
        employee = HrEmployee.objects.create(name='Con versión')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1), **version_kwargs,
        )
        employee.version = version
        employee.save()
        employee.refresh_from_db()
        return employee, version

    def test_current_version_matches_the_assigned_version(self):
        employee, version = self._employee_with_version()
        assert employee.current_version == version

    def test_current_date_version_matches_version_date_version(self):
        employee, version = self._employee_with_version()
        assert employee.current_date_version == date(2026, 1, 1)

    def test_versions_count_reflects_the_employee_history(self):
        employee, _version = self._employee_with_version()
        HrVersion.objects.create(employee=employee, date_version=date(2026, 6, 1))
        assert employee.versions_count == 2

    def test_contract_date_start_reads_through_version(self):
        employee, _version = self._employee_with_version(
            contract_date_start=date(2026, 1, 1),
        )
        assert employee.contract_date_start == date(2026, 1, 1)

    def test_contract_wage_reads_through_version(self):
        employee, _version = self._employee_with_version(wage=Decimal('22000.00'))
        assert employee.contract_wage == Decimal('22000.00')

    def test_department_reads_through_version(self):
        department = HrDepartment.objects.create(name='Recursos Humanos')
        employee, _version = self._employee_with_version(department=department)
        assert employee.department == department

    def test_job_title_reads_through_version(self):
        employee, _version = self._employee_with_version(job_title='Analista')
        assert employee.job_title == 'Analista'

    def test_is_current_reads_through_version(self):
        employee = HrEmployee.objects.create(name='Con versión vigente')
        version = HrVersion.objects.create(
            employee=employee, date_version=date.today(),
        )
        employee.version = version
        employee.save()
        employee.refresh_from_db()
        assert employee.is_current is True
