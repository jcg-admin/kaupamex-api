"""``search`` sobre un recordset de ``BaseModel`` — ≙ ``odoo19c:
odoo/orm/models.py:1363`` (``search``) y ``:5324`` (``_search``).

Casos propios del Consumer para las ramas que ``test_sort`` no ejerce: el
filtro de archivados (``active_test``), su anulación por dominio y por
contexto, la ventana ``offset``/``limit`` y ``search_count``.
"""

import pytest

from orm.environments import context_scope

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def records(env):
    rows = env['test_orm.model_active_field'].create(
        [{'name': name} for name in ('a', 'b', 'c')])
    rows[1].active = False
    env.flush_all()
    return rows


def test_archived_records_are_left_out_by_default(env, records):
    found = env['test_orm.model_active_field'].search(
        [('id', 'in', records.ids)], order='name')
    assert found.mapped('name') == ['a', 'c']


def test_naming_active_in_the_domain_lifts_the_filter(env, records):
    found = env['test_orm.model_active_field'].search(
        [('id', 'in', records.ids), ('active', '=', False)])
    assert found.mapped('name') == ['b']


def test_the_context_lifts_the_filter(env, records):
    with context_scope(active_test=False):
        found = env['test_orm.model_active_field'].search(
            [('id', 'in', records.ids)], order='name')
    assert found.mapped('name') == ['a', 'b', 'c']


def test_offset_limit_and_count(env, records):
    Model = env['test_orm.model_active_field']
    domain = [('id', 'in', records.ids)]
    assert Model.search(domain, order='name', offset=1, limit=1).mapped(
        'name') == ['c']
    assert Model.search_count(domain) == 2
