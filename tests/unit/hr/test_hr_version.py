"""``hr.version`` — la versión de carrera de un empleado (addon ``hr``).

Adaptación de Odoo hr/models/hr_version.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3). Ver el docstring del módulo (``addons/hr/models/hr_version.py``)
para el desenlace completo por símbolo y el hallazgo :ref:`h-api-690`.

Verificado por ORM directo en transacción con rollback antes de escribir
este archivo (tarea #513) — ver el hallazgo para la salida literal.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from addons.hr.models import HrEmployee, HrVersion

pytestmark = pytest.mark.django_db


class TestHrVersionUniqueActiveDateVersion:
    """≙ ``_check_unique_date_version`` (índice único parcial, ``:202-205``)."""

    def test_two_active_versions_same_employee_same_date_raise(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
        )
        with transaction.atomic(), pytest.raises(IntegrityError):
            HrVersion.objects.create(
                employee=employee, date_version=date(2026, 1, 1),
            )

    def test_two_versions_without_employee_same_date_are_allowed(self):
        # contract templates (employee=None) están excluidas del índice.
        HrVersion.objects.create(date_version=date(2026, 1, 1))
        HrVersion.objects.create(date_version=date(2026, 1, 1))


class TestHrVersionContractStartRequired:
    """≙ ``_check_contract_start_date_defined`` (``:197-200``)."""

    def test_contract_end_without_start_raises(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        with transaction.atomic(), pytest.raises(IntegrityError):
            HrVersion.objects.create(
                employee=employee, date_version=date(2026, 1, 1),
                contract_date_end=date(2026, 12, 31),
            )

    def test_contract_start_and_end_together_is_valid(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            contract_date_start=date(2026, 1, 1),
            contract_date_end=date(2026, 12, 31),
        )
        assert version.pk


class TestHrVersionDates:
    """≙ ``_compute_dates`` (``:561-580``) — property ``date_start``/``date_end``."""

    def test_date_start_defaults_to_date_version(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
        )
        assert version.date_start == date(2026, 1, 1)

    def test_date_start_is_the_max_of_version_and_contract_start(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            contract_date_start=date(2026, 1, 15),
        )
        assert version.date_start == date(2026, 1, 15)

    def test_date_end_is_the_day_before_the_next_version(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
        )
        HrVersion.objects.create(
            employee=employee, date_version=date(2026, 6, 1),
        )
        version.refresh_from_db()
        assert version.date_end == date(2026, 5, 31)

    def test_date_end_is_none_for_the_last_open_version(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
        )
        assert version.date_end is None


class TestHrVersionIsCurrentPastFuture:
    """≙ ``_compute_is_current``/``_compute_is_past``/``_compute_is_future``."""

    def test_a_version_starting_today_is_current(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date.today(),
        )
        assert version.is_current is True
        assert version.is_past is False
        assert version.is_future is False

    def test_a_version_starting_in_the_future_is_future(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2099, 1, 1),
        )
        assert version.is_future is True
        assert version.is_current is False


class TestHrVersionKmHomeWork:
    """≙ ``km_home_work`` (compute+inverse+store, ``:100-101``) — DIVERGENCIA:
    property+setter, mismo criterio que ``ResourceCalendar.flexible_hours``."""

    def test_km_conversion_from_miles(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            distance_home_work_unit=HrVersion.DistanceUnit.MILES,
            distance_home_work=10,
        )
        assert version.km_home_work == round(10 * 1.609)

    def test_km_setter_converts_back_to_miles(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            distance_home_work_unit=HrVersion.DistanceUnit.MILES,
        )
        version.km_home_work = 16
        assert version.distance_home_work == round(16 / 1.609)

    def test_km_equals_distance_when_unit_is_kilometers(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            distance_home_work_unit=HrVersion.DistanceUnit.KM,
            distance_home_work=42,
        )
        assert version.km_home_work == 42


class TestHrVersionContractWage:
    """≙ ``_get_contract_wage``/``_compute_contract_wage`` (``:460-469``)."""

    def test_contract_wage_reads_the_wage_field(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            wage=Decimal('18500.00'),
        )
        assert version.contract_wage == Decimal('18500.00')
        assert version._get_contract_wage_field() == 'wage'


class TestHrVersionCheckContractFinished:
    """≙ ``check_contract_finished`` (``:280-282``)."""

    def test_raises_when_contract_has_no_end_date(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            contract_date_start=date(2026, 1, 1),
        )
        with pytest.raises(ValueError):
            version.check_contract_finished()

    def test_does_not_raise_when_contract_is_closed(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
            contract_date_start=date(2026, 1, 1),
            contract_date_end=date(2026, 12, 31),
        )
        version.check_contract_finished()  # no debe levantar

    def test_does_not_raise_without_a_contract(self):
        employee = HrEmployee.objects.create(name='Ana Prueba')
        version = HrVersion.objects.create(
            employee=employee, date_version=date(2026, 1, 1),
        )
        version.check_contract_finished()  # no debe levantar


class TestHrVersionMaritalStatusSelection:
    """≙ ``_get_marital_status_selection`` (``:655-663``)."""

    def test_returns_the_five_reference_options(self):
        options = HrVersion._get_marital_status_selection()
        codes = {code for code, _label in options}
        assert codes == {'single', 'married', 'cohabitant', 'widower', 'divorced'}


class TestHrVersionStr:

    def test_str_falls_back_to_name_without_employee(self):
        version = HrVersion.objects.create(name='Plantilla base', date_version=date(2026, 1, 1))
        assert str(version) == 'Plantilla base'
