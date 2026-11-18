"""``hours_per_day`` y ``hours_per_week`` de ``resource.calendar`` como
calculados almacenados y editables.

≙ ``odoo19c: addons/resource/models/resource_calendar.py:102-106`` (los
campos), ``:210-221`` (los cómputos) y ``:692-707`` (``_get_hours_per_week``
y ``_get_hours_per_day``). Diseño en
``designs/project-sale-line-employee-map-port.md`` (paso H1).

*Métrica:* el valor de la columna leído con SQL, que no pasa por la caché
de la transacción, y el valor que devuelve el ORM.
*Ciega a:* el agrupamiento de ``display_cost`` sobre estas columnas, que es
del paso H2.
"""
import pytest
from django.apps import apps
from django.db import connection

from addons.base.models import ResCompany
from addons.resource.models import ResourceCalendar
from orm.environments import sudo
from orm.migration_operations import ComputeStoredFields

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def calendar():
    company = ResCompany.objects.create(code='acme-hours', name='ACME')
    record = ResourceCalendar.objects.create(name='Estándar', company=company)
    record.create_default_attendances()
    record.flush_model()
    return record


def _stored(calendar_id):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT hours_per_day, hours_per_week FROM resource_calendar '
            'WHERE id = %s', [calendar_id])
        # ``hours_per_day`` es ``numeric(2)``: el cursor lo devuelve Decimal.
        return tuple(float(value) for value in cursor.fetchone())


@pytest.mark.parametrize('name', ['hours_per_day', 'hours_per_week'])
def test_the_field_is_stored_computed_and_editable(name):
    field = ResourceCalendar._fields[name]
    assert field.store
    assert field.compute
    assert not field.readonly


def test_hours_per_week_is_not_copied():
    assert ResourceCalendar._fields['hours_per_week'].copy is False


def test_the_columns_hold_the_computed_hours(calendar):
    # 5 días * (4 h de mañana + 4 h de tarde): el descanso no cuenta.
    assert _stored(calendar.id) == (8.0, 40.0)
    assert (calendar.hours_per_day, calendar.hours_per_week) == (8.0, 40.0)


def test_editing_an_attendance_recomputes_the_hours(calendar):
    attendance = calendar.attendances.filtered(
        lambda a: a.day_period == 'afternoon')[:1]
    attendance.write({'hour_to': attendance.hour_to + 1})
    calendar.flush_model()
    assert _stored(calendar.id) == (8.2, 41.0)


def test_a_flexible_calendar_keeps_its_manual_hours(calendar):
    calendar.write({'schedule_type': 'flexible'})
    calendar.write({'hours_per_day': 6.0, 'hours_per_week': 30.0})
    attendance = calendar.attendances[:1]
    attendance.write({'hour_to': attendance.hour_to + 1})
    calendar.flush_model()
    assert _stored(calendar.id) == (6.0, 30.0)


def test_the_migration_fills_existing_rows(calendar):
    ResourceCalendar.objects.filter(pk=calendar.id).update(
        hours_per_day=0.0, hours_per_week=0.0)
    assert _stored(calendar.id) == (0.0, 0.0)
    with connection.schema_editor() as editor:
        ComputeStoredFields(
            'resource', 'resourcecalendar',
            ['hours_per_day', 'hours_per_week']).code(apps, editor)
    assert _stored(calendar.id) == (8.0, 40.0)
