"""``BaseModel._read_group_format_result`` y ``READ_GROUP_DISPLAY_FORMAT``.

≙ ``odoo19c: odoo/orm/models.py:315-333`` y ``:2554-2638``. Diseño en
``designs/read-group-format-result.md`` del Workbench.

*Métrica:* las filas formateadas sobre datos construidos en la prueba.
*Ciega a:* la rama ``properties`` (unidad 6e) y ``read_group`` (unidad 6d).
"""
import datetime

import pytest

import models
from orm.domains import Domain
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def _model(env, name, **context):
    model = env[name]._from_ids(env, (), ())
    return model.with_context(**context) if context else model


def _rows(group, *values):
    return [{group: value, '__domain': Domain.TRUE} for value in values]


def test_a_many2one_becomes_its_id_and_display_name(env):
    discussion = env['test_orm.discussion'].create({'name': 'first'})
    rows = _rows('discussion', discussion)
    _model(env, 'test_orm.message')._read_group_format_result(
        rows, ['discussion'])
    assert rows[0]['discussion'] == (discussion.id, 'first')
    assert rows[0]['__domain'] == [('discussion', '=', discussion.id)]


def test_an_empty_many2one_becomes_false(env):
    empty = env['test_orm.discussion']._from_ids(env, (), ())
    rows = _rows('discussion', empty)
    _model(env, 'test_orm.message')._read_group_format_result(
        rows, ['discussion'])
    assert rows[0]['discussion'] is False
    assert rows[0]['__domain'] == [('discussion', '=', False)]


def test_an_empty_many2many_group_matches_no_relation(env):
    empty = env['test_orm.category']._from_ids(env, (), ())
    rows = _rows('categories', empty)
    _model(env, 'test_orm.discussion')._read_group_format_result(
        rows, ['categories'])
    assert rows[0]['__domain'] == [('categories', 'not any', [])]


def test_a_month_gets_its_label_range_and_domain(env):
    rows = _rows('date:month', datetime.date(2026, 11, 1))
    _model(env, 'test_orm.mixed')._read_group_format_result(
        rows, ['date:month'])
    assert rows[0]['date:month'] == 'November 2026'
    assert rows[0]['__range'] == {
        'date:month': {'from': '2026-11-01', 'to': '2026-12-01'}}
    assert rows[0]['__domain'] == [
        '&', ('date', '>=', '2026-11-01'), ('date', '<', '2026-12-01')]


def test_a_week_label_uses_the_week_number(env):
    rows = _rows('date:week', datetime.date(2026, 11, 1))
    _model(env, 'test_orm.mixed')._read_group_format_result(
        rows, ['date:week'])
    assert rows[0]['date:week'] == 'W45 2026'


def test_a_datetime_range_is_converted_to_utc(env):
    rows = _rows('moment:day', datetime.datetime(2026, 3, 10))
    _model(env, 'test_orm.mixed', tz='America/Mexico_City'
           )._read_group_format_result(rows, ['moment:day'])
    assert rows[0]['__range'] == {'moment:day': {
        'from': '2026-03-10 06:00:00', 'to': '2026-03-11 06:00:00'}}


def test_an_empty_date_has_a_false_range(env):
    rows = _rows('date:month', False)
    _model(env, 'test_orm.mixed')._read_group_format_result(
        rows, ['date:month'])
    assert rows[0]['__range'] == {'date:month': False}
    assert rows[0]['__domain'] == [('date', '=', False)]


def test_a_number_granularity_filters_on_the_date_part(env):
    rows = _rows('date:year_number', 2026)
    _model(env, 'test_orm.mixed')._read_group_format_result(
        rows, ['date:year_number'])
    assert rows[0]['__domain'] == [('date.year_number', '=', 2026)]


def test_the_display_format_is_reexported_by_the_models_facade():
    assert models.READ_GROUP_DISPLAY_FORMAT['month'] == 'MMMM yyyy'
    assert models.READ_GROUP_DISPLAY_FORMAT['week'] == "'W'w YYYY"
