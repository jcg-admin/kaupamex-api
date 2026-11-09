"""EXPERIMENTAL — medición exploratoria del análisis de ``_search``.

Compara, fila por fila, los dos compiladores de dominio que conviven en el
árbol:

- el de Django: ``Domain._to_q`` → ``QuerySet.filter`` (lo que hoy hace
  ``BaseModel._search``);
- el de la referencia: ``Domain.optimize_full`` → ``Domain._to_sql`` sobre el
  ``Query`` portado (``tools.query.Query``), que es lo que hace
  ``odoo19c: odoo/orm/models.py:5324-5394``.

No es autoridad ni prueba de aceptación: produce la evidencia del diseño
``designs/search-contract-analysis.md``. Se ejecuta con pytest para heredar
la base de prueba y su transacción (las filas sembradas se descartan):

    W=scripts/workbench/orm-continuation-plan-20261103T095630
    PYTHONPATH=.:src uv run --frozen pytest \
        $W/probes/search_compiler_parity.py -q --reuse-db \
        -p no:cacheprovider -s

*Métrica:* el conjunto de ids de cada compilador por condición.
*Ciega a:* el orden de las filas y el coste; el plan se mide aparte con
``EXPLAIN``.
"""
import json
import pathlib
import sys

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.ir_rule import IrRule
from orm.domains import Domain, to_q
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.factories.user_factory import UserFactory
from tests.fixtures import model_domain_grid
from tools.query import Query
from tools.sql import SQL

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    """El entorno de superusuario, como en
    ``tests/integration/test_orm/conftest.py``."""
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


OUT = pathlib.Path(__file__).resolve().parent.parent / 'outputs' / \
    'search-contract'


def _django_ids(model, domain):
    # ``to_q`` optimiza a FULL antes de compilar, como hace ``_search``. La
    # primera versión llamaba a ``Domain._to_q`` sin optimizar y comparaba
    # así un árbol sin optimizar con otro optimizado: las 30 «distintas» de
    # esa medición eran del instrumento, no de los compiladores.
    return set(model.objects.filter(to_q(domain, model))
               .values_list('pk', flat=True))


def _sql_ids(env, model, domain):
    # Un BaseModel pasa su recordset vacío; un modelo de Django, su clase
    # (es la que lleva ``env``), como hace ``fields_relational``.
    record = model._from_ids(env, (), ()) if hasattr(model, '_from_ids') \
        else model
    domain = domain.optimize_full(record)
    if domain.is_false():
        return set(), None
    query = Query(env, model._meta.db_table,
                  SQL.identifier(model._meta.db_table))
    if not domain.is_true():
        query.add_where(domain._to_sql(record, query.table, query))
    sql = query.select(SQL.identifier(query.table, 'id'))
    return {row[0] for row in env.execute_query(sql)}, sql


def _compare(env, model, conditions):
    rows = []
    for condition in conditions:
        domain = Domain(*condition) if isinstance(condition, tuple) \
            else Domain(condition)
        entry = {'condition': repr(condition)}
        try:
            with transaction.atomic():
                entry['django'] = sorted(_django_ids(model, domain))
        except Exception as error:
            entry['django_error'] = (type(error).__name__ + ': '
                                     + str(error)[:160])
        try:
            with transaction.atomic():
                ids, sql = _sql_ids(env, model, domain)
            entry['sql'] = sorted(ids)
            if sql is not None:
                entry['sql_code'] = sql.code
                entry['sql_params'] = [repr(p) for p in sql.params]
        except Exception as error:
            entry['sql_error'] = type(error).__name__ + ': ' + str(error)[:160]
        entry['verdict'] = (
            'equal' if 'django' in entry and 'sql' in entry
            and entry['django'] == entry['sql'] else
            'differ' if 'django' in entry and 'sql' in entry else
            'only_django' if 'django' in entry else
            'only_sql' if 'sql' in entry else 'neither')
        rows.append(entry)
    return rows


def _write(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for row in rows:
        summary[row['verdict']] = summary.get(row['verdict'], 0) + 1
    (OUT / f'{name}.json').write_text(json.dumps(
        {'summary': summary, 'rows': rows}, indent=1, ensure_ascii=False))
    print(name, summary, file=sys.stderr)
    return summary


def _basemodel_grid():
    """La rejilla de ``model_domain_grid`` sobre campos de ``BaseModel`` del
    mismo tipo: los de ``ir.rule`` no sirven aquí porque ``ir.rule`` es un
    modelo de Django y el contrato de ``_search`` es de ``BaseModel``."""
    g = model_domain_grid
    message = [(field, operator, value)
               for field, operators, values in (
                   ('name', g.TEXT_OPERATORS, g.TEXT_VALUES),
                   ('important', g.BOOLEAN_OPERATORS, g.BOOLEAN_VALUES),
                   ('priority', g.INTEGER_OPERATORS, g.INTEGER_VALUES),
                   ('discussion', g.RELATIONAL_OPERATORS,
                    g.RELATIONAL_VALUES),
                   ('id', g.INTEGER_OPERATORS, g.INTEGER_VALUES))
               for operator in operators for value in values]
    discussion = [('categories', operator, value)
                  for operator in g.RELATIONAL_OPERATORS
                  for value in g.RELATIONAL_VALUES]
    return message, discussion


def test_grid_basemodel(env):
    first = env['test_orm.discussion'].create({'name': 'a'})
    second = env['test_orm.discussion'].create({'name': 'b'})
    category = env['test_orm.category'].create({'name': 'c'})
    env.execute_query(SQL(
        'INSERT INTO test_orm_discussion_category (discussion, category)'
        ' VALUES (%s, %s)', first.id, category.id))
    env['test_orm.message'].create([
        {'discussion': first.id, 'priority': 1, 'name': 'a',
         'important': True},
        {'discussion': second.id, 'priority': 2, 'name': ''},
        {'priority': 3, 'name': 'b'},
        {'discussion': first.id, 'priority': 1},
    ])
    message, discussion = _basemodel_grid()
    Message = type(env['test_orm.message'].browse(()))
    Discussion = type(env['test_orm.discussion'].browse(()))
    rows = _compare(env, Message, message) + \
        _compare(env, Discussion, discussion)
    _write('grid-basemodel', rows)


def test_grid_test_orm_message(env):
    discussion = env['test_orm.discussion'].create({'name': 'd'})
    other = env['test_orm.discussion'].create({'name': 'e'})
    env['test_orm.message'].create([
        {'discussion': discussion.id, 'priority': 1, 'name': 'a',
         'important': True},
        {'discussion': other.id, 'priority': 5, 'name': 'b'},
        {'discussion': discussion.id, 'priority': 9, 'name': 'c',
         'active': False},
    ])
    Message = type(env['test_orm.message'].browse(()))
    conditions = [
        ('priority', '>', 3), ('priority', 'in', [1, 9]),
        ('name', 'ilike', 'A'), ('important', '=', False),
        ('discussion.name', '=', 'd'), ('discussion', 'any',
                                        [('name', '=', 'e')]),
        ('discussion', 'not any', [('name', '=', 'e')]),
        ('discussion', '=', False), ('active', '=', False),
        ('id', 'in', []), ('discussion.messages.priority', '>', 4),
    ]
    _write('grid-test-orm-message', _compare(env, Message, conditions))


def test_rules_for_a_plain_user(env):
    label = env['test_orm.foo']._meta.label
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': 'test_orm.foo'})
    IrModelAccess.objects.create(name='probe read', model_id=row,
                                 perm_read=True)
    IrRule.objects.create(name='probe', model_name=label,
                          domain_force="[('value1', '>=', 2)]")
    foos = env['test_orm.foo'].create(
        [{'value1': 1}, {'value1': 2}, {'value1': 3}])
    rows = []
    with Environment(None, UserFactory().pk, {}) as plain:
        Foo = type(plain['test_orm.foo'].browse(()))
        current = set(Foo._search([]).values_list('pk', flat=True))
        # La fuente: Domain(safe_eval(rule.domain_force)) por regla
        # (odoo19c ir_rule.py:164); aquí _compute_domain devuelve un Q, así
        # que se arma el Domain de la única regla global como allá.
        sec = Domain([('value1', '>=', 2)])
        sudo_record = Foo._from_ids(plain, (), ())
        sec = sec.optimize_full(sudo_record)
        query = Query(plain, Foo._table, SQL.identifier(Foo._table))
        if not sec.is_true():
            query.add_where(sec._to_sql(sudo_record, Foo._table, query))
        sql = query.select(SQL.identifier(Foo._table, 'id'))
        by_sql = {r[0] for r in plain.execute_query(sql)}
        rows.append({'case': 'rule value1>=2', 'current_search':
                     sorted(current & set(foos.ids)),
                     'sql_rule': sorted(by_sql & set(foos.ids)),
                     'sql_code': sql.code, 'sql_params':
                     [repr(p) for p in sql.params],
                     'verdict': 'equal' if current == by_sql else 'differ'})
    _write('rules-plain-user', rows)


def test_sql_and_plan_of_the_rule_path(env):
    """Lo que emite hoy ``_search`` con una regla para un usuario normal,
    contra la consulta única de la fuente; con su plan real."""
    label = env['test_orm.foo']._meta.label
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': 'test_orm.foo'})
    IrModelAccess.objects.create(name='plan read', model_id=row,
                                 perm_read=True)
    IrRule.objects.create(name='plan', model_name=label,
                          domain_force="[('value1', '>=', 2)]")
    env['test_orm.foo'].create([{'value1': n % 5} for n in range(200)])
    report = {}
    with Environment(None, UserFactory().pk, {}) as plain:
        Foo = type(plain['test_orm.foo'].browse(()))
        with CaptureQueriesContext(connection) as captured:
            ids = list(Foo._search([('value1', '<', 4)]).values_list(
                'pk', flat=True))
        report['current'] = {
            'rows': len(ids), 'queries': len(captured.captured_queries),
            'sql': [q['sql'] for q in captured.captured_queries]}
        record = Foo._from_ids(plain, (), ())
        query = Query(plain, Foo._table, SQL.identifier(Foo._table))
        domain = Domain([('value1', '<', 4), ('active', '=', True)]
                        if 'active' in Foo._fields else
                        [('value1', '<', 4)]).optimize_full(record)
        query.add_where(domain._to_sql(record, Foo._table, query))
        sec = Domain([('value1', '>=', 2)]).optimize_full(record)
        query.add_where(sec._to_sql(record, Foo._table, query))
        select = query.select(SQL.identifier(Foo._table, 'id'))
        with CaptureQueriesContext(connection) as captured:
            ref_ids = [r[0] for r in plain.execute_query(select)]
        report['reference'] = {
            'rows': len(ref_ids), 'queries': len(captured.captured_queries),
            'sql': select.code, 'params': [repr(p) for p in select.params]}
        report['same_rows'] = sorted(ids) == sorted(ref_ids)
        for name, (code, params) in {
                'current_last': (report['current']['sql'][-1], None),
                'reference': (select.code, select.params)}.items():
            with connection.cursor() as cursor:
                if params is None:
                    cursor.execute('EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) '
                                   + code)
                else:
                    cursor.execute('EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) '
                                   + code, params)
                report['plan_' + name] = [r[0] for r in cursor.fetchall()]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'rule-path-sql-and-plan.json').write_text(
        json.dumps(report, indent=1, ensure_ascii=False))
    print('rule-path', report['current']['queries'],
          report['reference']['queries'], report['same_rows'],
          file=sys.stderr)
