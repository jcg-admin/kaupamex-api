"""``tools.query`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/query.py`` por ruta y se repite sobre los dos
módulos la misma secuencia de operaciones de ``Query``, comparando el SQL que
cada uno compone —su texto y sus parámetros— y las consultas que pide a su
``env``.

La fuente importa ``.sql`` de forma relativa, y la ``sql.py`` de la referencia
importa ``psycopg2`` y ``.misc``. Se registran durante la carga, y se retiran
después, tres sustitutos:

- un paquete sustituto que contiene la ``sql.py`` **de la referencia**;
- un ``psycopg2`` con la única excepción que ``sql.py`` nombra
  (``NotSupportedError``): este stack usa psycopg 3, y la ruta que la captura
  (``create_index``) no se ejercita aquí;
- un ``misc`` que expone ``named_to_positional_printf`` **del puerto**: el
  ``misc`` de la referencia arrastra media plataforma. Es la única pieza
  compartida, y sólo interviene al pasar parámetros con nombre a ``SQL``.

El ``env`` es un registrador: anota cada SQL que recibe en
``execute_query`` y devuelve filas fijas, porque la fuente sólo le pide eso.

La única divergencia que el puerto declara —su docstring, «La divergencia de
controlador»— se traduce antes de comparar, y se cuenta: donde la fuente pasa
una tupla a ``IN %s`` o a ``%s``, el puerto escribe ``= ANY(%s)`` o
``(SELECT unnest(%s))`` sobre una lista, porque psycopg 3 no expande una tupla
en una lista de ``IN``. Fuera de esas dos cadenas exactas no se traduce nada.

*Métrica:* para cada escenario, la secuencia de resultados —``SQL`` como
``(code, params)``, o el nombre de la excepción— y la secuencia de consultas
que llegan al ``env``.
*Ciega a:* la ejecución real contra PostgreSQL, a una divergencia en
``named_to_positional_printf`` (los dos lados usan la del puerto) y a toda
divergencia que la fuente comparta con nosotros.
"""
import importlib.util
import pathlib
import sys
import types

import pytest

from tools import misc as ported_misc
from tools import query as ported
from tools import sql as ported_sql

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_query', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

PACKAGE = 'reference_tools_package'
LONG = 'a_link_name_long_enough_to_exceed_the_identifier_limit_of_postgres'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reference_modules():
    """``(sql, query)`` de la fuente, o None si el árbol no está montado."""
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    tools = root / 'odoo' / 'tools'
    if not (tools / 'query.py').is_file():
        return None
    package = types.ModuleType(PACKAGE)
    package.__path__ = []
    misc = types.ModuleType(f'{PACKAGE}.misc')
    misc.named_to_positional_printf = ported_misc.named_to_positional_printf
    driver = types.ModuleType('psycopg2')
    driver.NotSupportedError = type('NotSupportedError', (Exception,), {})
    saved_driver = sys.modules.get('psycopg2')
    sys.modules.update({PACKAGE: package, f'{PACKAGE}.misc': misc,
                        'psycopg2': driver})
    try:
        sql = load(f'{PACKAGE}.sql', tools / 'sql.py')
        query = load(f'{PACKAGE}.query', tools / 'query.py')
        return sql, query
    finally:
        for name in [n for n in sys.modules if n.split('.')[0] == PACKAGE]:
            del sys.modules[name]
        if saved_driver is None:
            sys.modules.pop('psycopg2', None)
        else:
            sys.modules['psycopg2'] = saved_driver


@pytest.fixture(scope='module')
def reference():
    modules = reference_modules()
    if modules is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return modules


class Recorder:
    """El ``env`` de ``Query``: anota cada consulta y devuelve filas fijas."""

    def __init__(self, rows):
        self.rows = rows
        self.log = []

    def execute_query(self, sql):
        self.log.append(normalize(sql))
        return self.rows


def normalize(value):
    if hasattr(value, 'code') and hasattr(value, 'params'):
        return ('SQL', value.code, tuple(normalize(p) for p in value.params))
    if isinstance(value, (list, tuple)):
        return tuple(normalize(item) for item in value)
    return value


#: Las dos formas que el puerto declara, con su equivalente en la fuente.
DECLARED = (('= ANY(%s)', 'IN %s'), ('(SELECT unnest(%s))', '%s'))


def translate(value, counts):
    """Lleva al texto de la fuente las dos formas declaradas, y las cuenta."""
    if isinstance(value, tuple) and value[:1] == ('SQL',):
        code = value[1]
        for ours, theirs in DECLARED:
            if ours in code:
                counts[ours] = counts.get(ours, 0) + code.count(ours)
                code = code.replace(ours, theirs)
        return ('SQL', code, translate(value[2], counts))
    if isinstance(value, tuple):
        return tuple(translate(item, counts) for item in value)
    return value


def outcome(call):
    try:
        return ('value', normalize(call()))
    except Exception as error:
        return ('raises', type(error).__name__)


def scenario_joins(sql, query, env):
    q = query.Query(env, 'res_partner')
    steps = [
        q.add_where('res_partner.active'),
        q.add_where(sql.SQL('%s = %s', sql.SQL.identifier(
            'res_partner', 'name'), 'Acme')),
        q.join('res_partner', 'country_id', 'res_country', 'id',
               'country_id'),
        q.left_join('res_partner', 'parent_id', 'res_partner', 'id',
                    'parent_id'),
        q.join('res_partner', 'country_id', 'res_country', 'id',
               'country_id'),
        q.left_join('res_partner', 'x', 'res_users', 'partner_id', LONG),
        q.table, q.from_clause, q.where_clause, q.select(),
        q.select('id', sql.SQL('%s', 1)), q.subselect(), q.subselect('id'),
        str(q),
    ]
    q.order = 'res_partner.id DESC'
    q.limit, q.offset = 10, 5
    steps += [q.order, q.select(), q.subselect(), str(q)]
    return steps


def scenario_lazy_ids(sql, query, env):
    q = query.Query(env, 'res_partner')
    q.add_where('res_partner.active')
    steps = [q.is_empty(), bool(q), q.get_result_ids(), q.get_result_ids(),
             len(q), list(q), q.is_empty()]
    q.add_where('res_partner.id > 0')
    steps += [len(q), q.get_result_ids()]
    q.limit = 3
    steps.append(len(q))
    return steps


def scenario_set_ids(sql, query, env):
    q = query.Query(env, 'res_partner')
    q.set_result_ids([3, 1, 2])
    steps = [q.get_result_ids(), q.subselect(), q.subselect('id'),
             q.select(), len(q), bool(q), str(q)]
    # Cada llamada sobre una consulta virgen: la fuente lo exige con un
    # ``assert``, que ``scenario_errors`` mide aparte.
    q = query.Query(env, 'res_partner')
    q.set_result_ids([3, 1, 2], ordered=False)
    steps += [q.get_result_ids(), q.select(), q.subselect()]
    q = query.Query(env, 'res_partner')
    q.set_result_ids([])
    steps += [q.is_empty(), bool(q), q.subselect(), len(q), q.select()]
    q = query.Query(env, 'res_partner')
    q.set_result_ids([5])
    steps.append(outcome(lambda: q.set_result_ids([6])))
    return steps


def scenario_errors(sql, query, env):
    q = query.Query(env, 'res_partner')
    steps = [outcome(lambda: q.add_join('CROSS JOIN', 'x', 'x', sql.SQL()))]
    q.add_where('res_partner.active')
    steps.append(outcome(lambda: q.set_result_ids([1])))
    steps.append(outcome(lambda: q.add_table('res_partner')))
    other = query.Query(env, 'a', sql.SQL('(SELECT 1)'))
    other.add_table('b', sql.SQL('(SELECT 2)'))
    steps += [other.from_clause, other.select()]
    return steps


def scenario_helpers(sql, query, env):
    return [
        query._generate_table_alias('res_partner', 'country_id'),
        query._generate_table_alias('res_partner', LONG),
        query._generate_table_alias('a' * 60, 'b' * 10),
        query.Query.make_alias('res_partner', LONG),
        query._sql_from_table('t', sql.SQL.identifier('t')),
        query._sql_from_table('t', sql.SQL.identifier('u')),
        query._sql_from_join(sql.SQL('JOIN'), 't', sql.SQL.identifier('u'),
                             sql.SQL('%s', True)),
    ]


SCENARIOS = {
    'joins': (scenario_joins, [(1,), (2,)]),
    'lazy ids': (scenario_lazy_ids, [(4,), (5,)]),
    'set ids': (scenario_set_ids, [(7,)]),
    'errors': (scenario_errors, [(1,)]),
    'helpers': (scenario_helpers, []),
}


class TestQueryBehavesLikeTheReference:

    @pytest.mark.parametrize('name', sorted(SCENARIOS))
    def test_the_scenario_composes_the_same_sql(self, reference, name):
        their_sql, their_query = reference
        build, rows = SCENARIOS[name]
        their_env, our_env = Recorder(rows), Recorder(rows)
        expected = outcome(lambda: build(their_sql, their_query, their_env))
        counts = {}
        actual = translate(
            outcome(lambda: build(ported_sql, ported, our_env)), counts)
        assert expected[0] == 'value', expected
        assert actual == expected
        assert translate(tuple(our_env.log), counts) == tuple(their_env.log)
        if name == 'set ids':
            assert set(counts) == {ours for ours, _theirs in DECLARED}, (
                'la divergencia declarada dejó de aparecer: o el puerto la '
                'retiró, o el escenario ya no la ejercita')
        else:
            assert counts == {}, f'forma declarada fuera de su sitio: {counts}'

    def test_the_scenarios_reach_every_method(self, reference):
        _sql, their_query = reference
        declared = {name for name, value in vars(their_query.Query).items()
                    if callable(value) or isinstance(value, property)}
        source = pathlib.Path(__file__).read_text()
        missing = sorted(
            name for name in declared - {'__init__', '__iter__', '__len__',
                                         '__bool__', '__str__'}
            if f'.{name}' not in source)
        assert not missing, f'ningún escenario llama a {missing}'


class TestQueryLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_a_repeated_join_reuses_its_alias(self):
        q = ported.Query(Recorder([]), 'res_partner')
        first = q.join('res_partner', 'country_id', 'res_country', 'id', 'c')
        second = q.join('res_partner', 'country_id', 'res_country', 'id', 'c')
        assert first == second == 'res_partner__c'

    def test_known_ids_skip_the_database(self):
        env = Recorder([(9,)])
        q = ported.Query(env, 'res_partner')
        q.set_result_ids([2, 1])
        assert list(q) == [2, 1]
        assert env.log == []

    def test_a_limited_count_wraps_the_select(self):
        env = Recorder([(3,)])
        q = ported.Query(env, 'res_partner')
        q.limit = 3
        assert len(q) == 3
        assert 'LIMIT' in env.log[0][1]
