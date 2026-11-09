"""``BaseModel._read_group_fill_temporal`` — huecos de fechas rellenados.

≙ ``odoo19c: odoo/orm/models.py:2387-2552``. Diseño en
``designs/read-group-fill-temporal.md`` del Workbench.

*Métrica:* las listas devueltas sobre datos construidos en la prueba.
*Ciega a:* el agrupado por ``properties`` y el consumo desde ``read_group``.
"""
import datetime

import pytest
import pytz

from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

COUNT = {'__count': '__count'}


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def _model(env, **context):
    model = env['test_orm.mixed']._from_ids(env, (), ())
    return model.with_context(**context) if context else model


def _months(rows, key='date:month'):
    return [(row[key], row['__count']) for row in rows]


def test_a_non_temporal_groupby_is_returned_unchanged(env):
    data = [{'number': 1, '__count': 3}]
    assert _model(env)._read_group_fill_temporal(
        data, ['number'], COUNT) is data


def test_the_months_between_existing_groups_are_filled(env):
    data = [{'date:month': datetime.date(2026, 6, 1), '__count': 2},
            {'date:month': datetime.date(2026, 9, 1), '__count': 1}]
    rows = _model(env)._read_group_fill_temporal(
        data, ['date:month'], COUNT)
    assert _months(rows) == [
        (datetime.date(2026, 6, 1), 2), (datetime.date(2026, 7, 1), 0),
        (datetime.date(2026, 8, 1), 0), (datetime.date(2026, 9, 1), 1)]


def test_explicit_bounds_fill_before_and_after(env):
    data = [{'date:month': datetime.date(2026, 9, 1), '__count': 1}]
    rows = _model(env)._read_group_fill_temporal(
        data, ['date:month'], COUNT,
        fill_from='2026-08-15', fill_to='2026-10-20')
    assert _months(rows) == [
        (datetime.date(2026, 8, 1), 0), (datetime.date(2026, 9, 1), 1),
        (datetime.date(2026, 10, 1), 0)]


def test_min_groups_extends_from_the_lower_bound(env):
    data = [{'date:month': datetime.date(2026, 9, 1), '__count': 1}]
    rows = _model(env)._read_group_fill_temporal(
        data, ['date:month'], COUNT, fill_from='2026-08-01', min_groups=4)
    assert [day for day, _count in _months(rows)] == [
        datetime.date(2026, month, 1) for month in (8, 9, 10, 11)]


def test_without_data_or_bounds_nothing_is_returned(env):
    assert _model(env)._read_group_fill_temporal(
        [], ['date:month'], COUNT) == []


def test_the_false_group_goes_last(env):
    data = [{'date:month': False, '__count': 4},
            {'date:month': datetime.date(2026, 6, 1), '__count': 1},
            {'date:month': datetime.date(2026, 7, 1), '__count': 1}]
    rows = _model(env)._read_group_fill_temporal(
        data, ['date:month'], COUNT)
    assert _months(rows) == [(datetime.date(2026, 6, 1), 1),
                             (datetime.date(2026, 7, 1), 1), (False, 4)]


def test_the_other_groupbys_take_their_empty_value(env):
    data = [{'date:month': datetime.date(2026, 6, 1), 'number': 3,
             '__count': 1},
            {'date:month': datetime.date(2026, 8, 1), 'number': 5,
             '__count': 1}]
    rows = _model(env)._read_group_fill_temporal(
        data, ['date:month', 'number'], COUNT)
    assert rows[1] == {'date:month': datetime.date(2026, 7, 1),
                       'number': False, '__count': 0}


def test_datetime_bounds_are_localized_in_the_context_zone(env):
    zone = pytz.timezone('America/Mexico_City')
    rows = _model(env, tz='America/Mexico_City')._read_group_fill_temporal(
        [], ['moment:month'], COUNT,
        fill_from=datetime.datetime(2026, 3, 10, 8, 0),
        fill_to=datetime.datetime(2026, 4, 2, 8, 0))
    assert [row['moment:month'] for row in rows] == [
        zone.localize(datetime.datetime(2026, 3, 1)),
        zone.localize(datetime.datetime(2026, 4, 1))]


def test_weeks_start_on_the_language_first_day(env):
    rows = _model(env)._read_group_fill_temporal(
        [], ['date:week'], COUNT,
        fill_from='2026-11-04', fill_to='2026-11-11')
    days = [row['date:week'] for row in rows]
    assert days == [datetime.date(2026, 11, 1), datetime.date(2026, 11, 8)]
    assert {day.isoweekday() for day in days} == {7}
