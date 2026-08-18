"""``hr.employee`` × ``hr.version`` — la familia (a) reconectada (tarea #524).

Ejercita los 24 métodos que el porte de ``hr_employee.py`` recuperó al existir
``hr.version`` (``addons/hr/models/hr_version.py``, ``api@87d00e6`` +
``api@aaef255``). Adaptación de Odoo hr/models/hr_employee.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

La premisa que estos casos verifican, y que motivó la tarea, es que **no es
delegación** a ``self.version``: la mayoría agrega sobre **todo** el historial
(``self.versions``, el reverso de ``hr.HrVersion.employee``). Por eso cada
clase de abajo que toca contrato o antigüedad construye al menos **dos**
versiones y comprueba el resultado del conjunto, no el de la vigente.

Creado: 2026-08-18T23:11:21.
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from addons.hr.models import HrEmployee, HrVersion

pytestmark = pytest.mark.django_db


def _employee(name='Ana Prueba'):
    return HrEmployee.objects.create(name=name)


def _version(employee, date_version, **kwargs):
    return HrVersion.objects.create(
        employee=employee, date_version=date_version, **kwargs,
    )


class TestGetVersion:
    """≙ ``_get_version`` (``:557-567``)."""

    def test_returns_the_version_effective_at_the_date(self):
        employee = _employee()
        first = _version(employee, date(2026, 1, 1))
        second = _version(employee, date(2026, 6, 1))

        assert employee._get_version(date(2026, 3, 1)) == first
        assert employee._get_version(date(2026, 7, 1)) == second

    def test_falls_back_to_the_earliest_version_when_none_applies(self):
        employee = _employee()
        first = _version(employee, date(2026, 5, 1))

        assert employee._get_version(date(2026, 1, 1)) == first

    def test_returns_none_without_history(self):
        assert _employee()._get_version(date(2026, 1, 1)) is None


class TestCurrentVersion:
    """≙ ``_compute_current_version_id`` (``:526-540``) y su cron."""

    def test_save_points_the_foreign_key_at_the_newest_past_version(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1))
        newest = _version(employee, date(2021, 1, 1))
        # Una versión futura NO debe ganar.
        _version(employee, date(2999, 1, 1))

        employee.save()
        employee.refresh_from_db()

        assert employee.version_id == newest.pk
        assert employee.current_version == newest

    def test_cron_updates_every_employee_whose_version_changed(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1))
        employee.save()
        newest = _version(employee, date(2021, 1, 1))

        updated = HrEmployee._cron_update_current_version_id()
        employee.refresh_from_db()

        assert updated >= 1
        assert employee.version_id == newest.pk


class TestContractDatesOverTheWholeHistory:
    """≙ ``_get_all_contract_dates`` / ``_get_contract_dates`` /
    ``_is_in_contract`` (``:753-772``, ``:667-668``).

    Este es el caso que prueba la premisa de #524: los tres agregan sobre
    **varias** versiones, no sobre ``self.version``.
    """

    def test_all_contract_dates_collects_every_version_interval(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1),
                 contract_date_start=date(2020, 1, 1),
                 contract_date_end=date(2020, 12, 31))
        _version(employee, date(2022, 1, 1),
                 contract_date_start=date(2022, 1, 1),
                 contract_date_end=date(2022, 12, 31))
        # Una versión sin contrato no aporta intervalo.
        _version(employee, date(2023, 1, 1))
        employee.save()

        assert employee._get_all_contract_dates() == [
            (date(2020, 1, 1), date(2020, 12, 31)),
            (date(2022, 1, 1), date(2022, 12, 31)),
        ]

    def test_two_versions_of_the_same_contract_yield_one_interval(self):
        """Control de H-API-713 — el orden por defecto de ``HrVersion``
        se colaba en el ``SELECT DISTINCT`` y duplicaba el intervalo."""
        employee = _employee()
        _version(employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))
        _version(employee, date(2026, 6, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))

        assert employee._get_all_contract_dates() == [
            (date(2026, 1, 1), date(2026, 12, 31)),
        ]

    def test_contract_dates_finds_the_old_interval_not_only_the_current(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1),
                 contract_date_start=date(2020, 1, 1),
                 contract_date_end=date(2020, 12, 31))
        _version(employee, date(2022, 1, 1),
                 contract_date_start=date(2022, 1, 1),
                 contract_date_end=date(2022, 12, 31))
        employee.save()

        # La versión vigente es la de 2022; la respuesta correcta para 2020
        # sale del historial completo.
        assert employee._get_contract_dates(date(2020, 6, 1)) == (
            date(2020, 1, 1), date(2020, 12, 31),
        )
        assert employee._is_in_contract(date(2020, 6, 1)) is True
        assert employee._is_in_contract(date(2021, 6, 1)) is False

    def test_open_ended_contract_has_no_end(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1), contract_date_start=date(2020, 1, 1))

        assert employee._get_contract_dates(date(2999, 1, 1)) == (
            date(2020, 1, 1), None,
        )

    def test_without_contract_the_answer_is_the_empty_pair(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1))

        assert employee._get_contract_dates(date(2020, 6, 1)) == (None, None)


class TestCheckNoExistingContract:
    """≙ ``check_no_existing_contract`` (``:385-391``)."""

    def test_raises_inside_an_existing_contract(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))

        with pytest.raises(Exception) as excinfo:
            employee.check_no_existing_contract(date(2026, 6, 1))
        assert 'contrato' in str(excinfo.value)

    def test_accepts_a_date_outside_every_contract(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))

        assert employee.check_no_existing_contract(date(2027, 6, 1)) is None

    def test_accepts_an_iso_string(self):
        assert _employee().check_no_existing_contract('2026-06-01') is None


class TestFirstVersions:
    """≙ ``_get_first_versions*`` (``:453-495``) — el corte por hueco."""

    def test_a_gap_of_four_days_or_more_cuts_the_series(self):
        employee = _employee()
        # Ocupación antigua, cerrada, seguida de un hueco largo.
        _version(employee, date(2018, 1, 1),
                 contract_date_start=date(2018, 1, 1),
                 contract_date_end=date(2018, 12, 31))
        # Ocupación actual, dos versiones contiguas.
        _version(employee, date(2024, 1, 1),
                 contract_date_start=date(2024, 1, 1),
                 contract_date_end=date(2024, 12, 31))
        _version(employee, date(2025, 1, 1),
                 contract_date_start=date(2025, 1, 1),
                 contract_date_end=date(2025, 12, 31))

        versions = employee._get_first_versions_filtered()
        starts = sorted(version.date_start for version in versions)

        assert date(2018, 1, 1) not in starts
        assert employee._get_first_version_date() == date(2024, 1, 1)
        assert employee._get_first_contract_date() == date(2024, 1, 1)

    def test_without_gap_filtering_the_whole_history_counts(self):
        employee = _employee()
        _version(employee, date(2018, 1, 1),
                 contract_date_start=date(2018, 1, 1),
                 contract_date_end=date(2018, 12, 31))
        _version(employee, date(2024, 1, 1),
                 contract_date_start=date(2024, 1, 1))

        assert employee._get_first_version_date(no_gap=False) == date(2018, 1, 1)
        assert len(employee._get_first_versions()) == 2

    def test_before_date_narrows_the_history(self):
        employee = _employee()
        _version(employee, date(2018, 1, 1))
        _version(employee, date(2024, 1, 1))

        narrowed = employee._get_first_versions(before_date=date(2020, 1, 1))

        assert len(narrowed) == 1
        assert narrowed[0].date_version == date(2018, 1, 1)


class TestContractVersionsGrouping:
    """≙ ``_get_contract_versions`` / ``_get_contracts`` (``:670-751``)."""

    def test_versions_group_by_contract_start_across_two_employees(self):
        first_employee = _employee('Ana Prueba')
        second_employee = _employee('Beto Prueba')
        _version(first_employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))
        _version(first_employee, date(2026, 6, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))
        _version(second_employee, date(2026, 3, 1),
                 contract_date_start=date(2026, 3, 1))

        grouped = HrEmployee._get_contract_versions(
            [first_employee, second_employee],
        )

        assert set(grouped) == {first_employee.pk, second_employee.pk}
        # Las dos versiones del primer empleado pertenecen al MISMO contrato.
        assert list(grouped[first_employee.pk]) == [date(2026, 1, 1)]
        assert len(grouped[first_employee.pk][date(2026, 1, 1)]) == 2

    def test_contracts_pick_the_latest_version_of_each_contract(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))
        latest = _version(employee, date(2026, 6, 1),
                          contract_date_start=date(2026, 1, 1),
                          contract_date_end=date(2026, 12, 31))

        contracts = HrEmployee._get_contracts([employee])

        assert contracts[employee.pk] == [latest]

    def test_a_version_without_contract_is_left_out(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1))

        assert HrEmployee._get_contract_versions([employee]) == {}


class TestOverlapWithPeriod:
    """≙ ``_get_versions_with_contract_overlap_with_period`` (``:1767-1775``)."""

    def test_only_versions_overlapping_the_period_come_back(self):
        employee = _employee()
        old = _version(employee, date(2020, 1, 1),
                       contract_date_start=date(2020, 1, 1),
                       contract_date_end=date(2020, 12, 31))
        current = _version(employee, date(2026, 1, 1),
                           contract_date_start=date(2026, 1, 1),
                           contract_date_end=date(2026, 12, 31))

        overlapping = employee._get_versions_with_contract_overlap_with_period(
            date(2026, 1, 1), date(2026, 12, 31),
        )

        assert current in overlapping
        assert old not in overlapping

    def test_the_class_level_sweep_covers_every_employee(self):
        first_employee = _employee('Ana Prueba')
        second_employee = _employee('Beto Prueba')
        _version(first_employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1))
        _version(second_employee, date(2026, 2, 1),
                 contract_date_start=date(2026, 2, 1))

        found = HrEmployee._get_all_versions_with_contract_overlap_with_period(
            date(2026, 1, 1), date(2026, 12, 31),
        )
        owners = {version.employee_id for version in found}

        assert {first_employee.pk, second_employee.pk} <= owners


class TestCreateVersion:
    """≙ ``create_version`` (``:569-640``)."""

    def test_copies_the_effective_version_and_applies_the_new_values(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1), job_title='Analista',
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))

        created = employee.create_version({
            'date_version': date(2026, 6, 1), 'job_title': 'Analista senior',
        })

        assert created.job_title == 'Analista senior'
        # El contrato vigente viaja con la copia.
        assert created.contract_date_start == date(2026, 1, 1)
        assert created.contract_date_end == date(2026, 12, 31)
        assert employee.versions.count() == 2

    def test_an_existing_version_on_the_same_date_is_not_duplicated(self):
        employee = _employee()
        existing = _version(employee, date(2026, 1, 1))

        created = employee.create_version({'date_version': date(2026, 1, 1)})

        assert created == existing
        assert employee.versions.count() == 1

    def test_a_new_contract_end_propagates_to_the_whole_contract(self):
        employee = _employee()
        first = _version(employee, date(2026, 1, 1),
                         contract_date_start=date(2026, 1, 1),
                         contract_date_end=date(2026, 12, 31))
        second = _version(employee, date(2026, 3, 1),
                          contract_date_start=date(2026, 1, 1),
                          contract_date_end=date(2026, 12, 31))

        employee.create_version({
            'date_version': date(2026, 6, 1),
            'contract_date_end': date(2026, 9, 30),
        })
        first.refresh_from_db()
        second.refresh_from_db()

        assert first.contract_date_end == date(2026, 9, 30)
        assert second.contract_date_end == date(2026, 9, 30)

    def test_an_iso_string_date_version_is_accepted(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1))

        created = employee.create_version({'date_version': '2026-06-01'})

        assert created.date_version == date(2026, 6, 1)

    def test_without_date_version_it_raises(self):
        with pytest.raises(ValueError):
            _employee().create_version({'job_title': 'Analista'})


class TestCreateContract:
    """≙ ``create_contract`` (``:643-665``)."""

    def test_writes_the_dates_on_the_version_of_the_same_date(self):
        employee = _employee()
        existing = _version(employee, date(2026, 1, 1))

        result = employee.create_contract(date(2026, 1, 1))
        existing.refresh_from_db()

        assert result == existing
        assert existing.contract_date_start == date(2026, 1, 1)
        assert existing.contract_date_end is None

    def test_a_future_contract_closes_the_new_one_the_day_before(self):
        employee = _employee()
        _version(employee, date(2026, 9, 1),
                 contract_date_start=date(2026, 9, 1),
                 contract_date_end=date(2026, 12, 31))

        created = employee.create_contract(date(2026, 1, 1))

        assert created.contract_date_start == date(2026, 1, 1)
        assert created.contract_date_end == date(2026, 8, 31)


class TestDepartureDate:
    """≙ ``_get_departure_date`` (``:1759-1765``)."""

    def test_a_finished_contract_yields_the_departure_date(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1),
                 contract_date_start=date(2020, 1, 1),
                 contract_date_end=date(2020, 12, 31),
                 departure_date=date(2020, 12, 31))
        employee.save()

        assert employee._get_departure_date() == date(2020, 12, 31)

    def test_a_live_contract_yields_nothing(self):
        employee = _employee()
        _version(employee, date(2020, 1, 1),
                 contract_date_start=date(2020, 1, 1),
                 departure_date=date(2020, 12, 31))
        employee.save()

        assert employee._get_departure_date() is None


class TestWorkLocationColumns:
    """≙ ``_compute_work_location_name`` / ``_compute_work_location_type``
    (``:515-524``) — materializados en ``save()``."""

    def test_without_version_both_columns_stay_empty(self):
        employee = _employee()
        employee.save()

        assert employee.work_location_name == ''
        assert employee.work_location_type == ''


class TestTimezone:
    """≙ ``_get_tz`` / ``_get_tz_batch`` (``:1545-1556``)."""

    def test_falls_back_to_utc_without_calendar_or_company(self):
        employee = _employee()

        assert employee._get_tz() == 'UTC'

    def test_the_batch_maps_every_employee_by_primary_key(self):
        first_employee = _employee('Ana Prueba')
        second_employee = _employee('Beto Prueba')

        mapping = HrEmployee._get_tz_batch([first_employee, second_employee])

        assert set(mapping) == {first_employee.pk, second_employee.pk}
        assert set(mapping.values()) == {'UTC'}


class TestVersionPeriods:
    """≙ ``_get_version_periods`` / ``_get_calendar_periods``
    (``:1594-1631``)."""

    def test_each_version_contributes_its_slice_of_the_window(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))
        _version(employee, date(2026, 7, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))

        start = datetime.combine(date(2026, 1, 1), time.min, tzinfo=ZoneInfo('UTC'))
        stop = datetime.combine(date(2026, 12, 31), time.max, tzinfo=ZoneInfo('UTC'))
        periods = HrEmployee._get_version_periods(
            [employee], start, stop, check_contract=True,
        )

        assert len(periods[employee.pk]) == 2

    def test_an_unknown_field_raises(self):
        employee = _employee()
        start = datetime.combine(date(2026, 1, 1), time.min, tzinfo=ZoneInfo('UTC'))
        stop = datetime.combine(date(2026, 12, 31), time.max, tzinfo=ZoneInfo('UTC'))

        with pytest.raises(Exception) as excinfo:
            HrEmployee._get_version_periods(
                [employee], start, stop, field='no_existe',
            )
        assert 'no_existe' in str(excinfo.value)

    def test_calendar_periods_carry_the_calendar_as_the_value(self):
        employee = _employee()
        _version(employee, date(2026, 1, 1),
                 contract_date_start=date(2026, 1, 1),
                 contract_date_end=date(2026, 12, 31))

        start = datetime.combine(date(2026, 1, 1), time.min, tzinfo=ZoneInfo('UTC'))
        stop = datetime.combine(date(2026, 12, 31), time.max, tzinfo=ZoneInfo('UTC'))
        periods = HrEmployee._get_calendar_periods([employee], start, stop)

        assert len(periods[employee.pk]) == 1
        # Sin calendario en la versión, el valor del tramo es None.
        assert periods[employee.pk][0][2] is None
