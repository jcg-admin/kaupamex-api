"""``Environment.execute_query`` vuelca los campos que la consulta declara.

≙ ``odoo19c: odoo/orm/environments.py:515-535``: *"The method
automatically flushes all the fields in the metadata of the query"*. Un
calculado almacenado pendiente se lee calculado, no la columna vieja.
Diseño en ``designs/execute-query-flush.md``.

*Métrica:* el valor que devuelve la consulta mientras el cómputo está
pendiente en la caché.
*Ciega a:* el coste del volcado en consultas calientes.
"""
import pytest

from addons.base.models import ResCompany
from addons.resource.models import ResourceCalendar
from orm.environments import env as current_env
from orm.environments import sudo
from tools.sql import SQL

pytestmark = pytest.mark.django_db


@pytest.fixture
def calendar():
    """Un calendario de 40 h en cinco días, sin volcar: ``hours_per_day``
    está pendiente en la caché y la columna vale 0."""
    with sudo():
        company = ResCompany.objects.create(code='acme-flush', name='ACME')
        record = ResourceCalendar.objects.create(name='Est', company=company)
        record.create_default_attendances()
        yield record


def _select_hours(calendar):
    field = ResourceCalendar._fields['hours_per_day']
    return SQL('SELECT %s FROM resource_calendar WHERE id = %s',
               SQL.identifier('resource_calendar', 'hours_per_day',
                              to_flush=field),
               calendar.id)


def test_execute_query_flushes_a_pending_stored_compute(calendar):
    with sudo():
        [(hours,)] = current_env().execute_query(_select_hours(calendar))
    assert float(hours) == 8.0


def test_execute_query_dict_flushes_a_pending_stored_compute(calendar):
    with sudo():
        [row] = current_env().execute_query_dict(_select_hours(calendar))
    assert float(row['hours_per_day']) == 8.0


def test_read_group_aggregates_the_computed_value(calendar):
    with sudo():
        rows = current_env()['resource.calendar']._read_group(
            [('id', 'in', [calendar.id])], ['hours_per_day'],
            ['id:array_agg'])
    assert [(float(hours), ids) for hours, ids in rows] == [
        (8.0, [calendar.id])]
