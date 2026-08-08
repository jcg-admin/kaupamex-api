"""``resource.calendar`` + ``resource.calendar.attendance`` (addon
``resource``, cierre parcial — sin motor de intervalos, ver
``resource_calendar.py``).

Adaptación fiel de Odoo resource/models/resource_calendar{,_attendance}.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
from datetime import date

import pytest

from addons.base.models import ResCompany
from addons.resource.models import (
    ResourceCalendar, ResourceCalendarAttendance, ResourceResource,
)
from exceptions import ValidationError

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme-resource', name='ACME')


@pytest.fixture
def calendar(company):
    return ResourceCalendar.objects.create(name='Horario estándar', company=company)


class TestResourceCalendarAttendance:
    def test_duration_hours_from_hour_range(self, calendar):
        attendance = ResourceCalendarAttendance.objects.create(
            name='Lunes mañana', calendar=calendar, dayofweek='0',
            hour_from=8, hour_to=12, day_period='morning',
        )
        assert attendance.duration_hours == 4

    def test_duration_hours_is_zero_for_lunch(self, calendar):
        attendance = ResourceCalendarAttendance.objects.create(
            name='Lunes descanso', calendar=calendar, dayofweek='0',
            hour_from=12, hour_to=13, day_period='lunch',
        )
        assert attendance.duration_hours == 0

    def test_is_work_period_excludes_lunch(self, calendar):
        work = ResourceCalendarAttendance.objects.create(
            name='Lunes mañana', calendar=calendar, dayofweek='0',
            hour_from=8, hour_to=12, day_period='morning',
        )
        lunch = ResourceCalendarAttendance.objects.create(
            name='Lunes descanso', calendar=calendar, dayofweek='0',
            hour_from=12, hour_to=13, day_period='lunch',
        )
        assert work.is_work_period is True
        assert lunch.is_work_period is False

    def test_get_week_type_parity(self):
        # Odoo: paridad de (ordinal - 1) // 7. Verificado contra el propio
        # algoritmo de la referencia (no hay tabla externa que consultar).
        day_a = date(2026, 1, 5)
        day_b = day_a.replace(day=12)
        assert ResourceCalendarAttendance.get_week_type(day_a) != \
            ResourceCalendarAttendance.get_week_type(day_b)

    def test_copy_vals_round_trips_into_new_attendance(self, calendar, company):
        source = ResourceCalendarAttendance.objects.create(
            name='Martes tarde', calendar=calendar, dayofweek='1',
            hour_from=13, hour_to=17, day_period='afternoon', sequence=20,
        )
        other_calendar = ResourceCalendar.objects.create(
            name='Otro horario', company=company,
        )
        clone = ResourceCalendarAttendance.objects.create(
            calendar=other_calendar, **source.copy_vals(),
        )
        assert clone.name == source.name
        assert clone.hour_from == source.hour_from
        assert clone.hour_to == source.hour_to


class TestResourceCalendarValidation:
    def test_check_attendances_raises_on_overlap(self, calendar):
        ResourceCalendarAttendance.objects.create(
            name='A', calendar=calendar, dayofweek='0',
            hour_from=8, hour_to=12, day_period='morning',
        )
        ResourceCalendarAttendance.objects.create(
            name='B', calendar=calendar, dayofweek='0',
            hour_from=11, hour_to=15, day_period='afternoon',
        )
        with pytest.raises(ValidationError):
            calendar.check_attendances()

    def test_check_attendances_passes_without_overlap(self, calendar):
        ResourceCalendarAttendance.objects.create(
            name='A', calendar=calendar, dayofweek='0',
            hour_from=8, hour_to=12, day_period='morning',
        )
        ResourceCalendarAttendance.objects.create(
            name='B', calendar=calendar, dayofweek='0',
            hour_from=13, hour_to=17, day_period='afternoon',
        )
        calendar.check_attendances()  # no debe levantar


class TestResourceCalendarAggregates:
    def test_hours_per_week_sums_work_attendances_only(self, calendar):
        calendar.create_default_attendances()
        # 5 días * (4h mañana + 4h tarde) = 40h; el descanso no cuenta.
        assert calendar.hours_per_week == 40

    def test_hours_per_day_divides_by_days_worked(self, calendar):
        calendar.create_default_attendances()
        assert calendar.hours_per_day == 8

    def test_flexible_hours_setter_writes_schedule_type(self, calendar):
        calendar.flexible_hours = True
        assert calendar.schedule_type == 'flexible'
        assert calendar.hours_per_week == 0

    def test_work_time_rate_full_time(self, calendar):
        calendar.create_default_attendances()
        calendar.full_time_required_hours = 40
        assert calendar.work_time_rate == 100
        assert calendar.is_fulltime is True

    def test_work_resources_count_reflects_linked_resources(self, calendar):
        assert calendar.work_resources_count == 0
        ResourceResource.objects.create(name='Máquina 1', calendar=calendar)
        assert calendar.work_resources_count == 1


class TestResourceCalendarDefaultForCompany:
    def test_company_extension_creates_default_calendar(self, company):
        assert company.resource_calendar is None
        calendar = company.get_or_create_default_resource_calendar()
        assert calendar.is_default is True
        assert calendar.company_id == company.pk
        assert calendar.attendances.count() == 15  # 5 días * 3 tramos
        # Idempotente: una segunda llamada no crea otro calendario.
        assert company.get_or_create_default_resource_calendar().pk == calendar.pk

    def test_resource_calendars_reverse_accessor(self, company, calendar):
        assert list(company.resource_calendars.all()) == [calendar]


class TestResourceCalendarSwitchModes:
    def test_switch_calendar_type_enables_two_weeks(self, calendar):
        calendar.create_default_attendances()
        calendar.switch_calendar_type()
        assert calendar.two_weeks_calendar is True
        week_types = {a.week_type for a in calendar.attendances.all() if a.week_type}
        assert week_types == {'0', '1'}

    def test_switch_calendar_type_round_trips_to_single_week(self, calendar):
        calendar.create_default_attendances()
        calendar.switch_calendar_type()
        calendar.switch_calendar_type()
        assert calendar.two_weeks_calendar is False
        assert calendar.attendances.count() == 15
