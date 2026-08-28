"""Contrato de ``tools.query.Query`` — tarea #127.

Cierra el porte de ``src/tools/query.py`` contra ``odoo19c:
odoo/tools/query.py`` (24 símbolos, 0 ausentes). Hasta ``api@38b4e64e`` este
archivo era ``Query = models.QuerySet``: la equivalencia declarada y ninguna
de las dos operaciones que la cadena de ``_field_to_sql`` necesita —
``make_alias`` y ``add_join``—.

Tres bloques:

1. **Los 24 símbolos** de la referencia, por nombre.
2. **El SQL que emite**, comparado con la forma de la fuente.
3. **El recorte de alias**, que es la razón por la que ``make_identifier``
   salió de la lista de ausentes de ``tools/sql.py``.
"""
import ast
import pathlib

import pytest
from django.apps import apps
from django.db.models import QuerySet

from addons.base.models import ResPartner
from tools import query as query_module
from tools.query import Query
from tools.sql import SQL, make_identifier


def symbols_of(path):
    """Los símbolos de nivel de módulo y de clase declarados en ``path``."""
    tree = ast.parse(pathlib.Path(path).read_text())
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.add(node.name)
        elif isinstance(node, ast.ClassDef):
            found.add(node.name)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.add(child.name)
    return found


REFERENCE_SYMBOLS = (
    '_sql_from_table', '_sql_from_join', '_generate_table_alias', 'Query',
    '__init__', 'make_alias', 'add_table', 'add_join', 'add_where', 'join',
    'left_join', 'order', 'table', 'from_clause', 'where_clause', 'is_empty',
    'select', 'subselect', 'get_result_ids', 'set_result_ids',
    '__str__', '__bool__', '__len__', '__iter__',
)


class TestPortedSymbols:
    """Los 24 que la referencia declara, con su nombre."""

    @pytest.mark.parametrize('name', REFERENCE_SYMBOLS)
    def test_the_reference_symbol_is_declared_here(self, name):
        assert name in symbols_of(query_module.__file__)

    def test_no_symbol_of_the_reference_is_missing(self):
        # El conteo va con su población: 24 de 24, medido por AST.
        assert set(REFERENCE_SYMBOLS) <= symbols_of(query_module.__file__)

    def test_query_is_no_longer_an_alias_of_the_django_queryset(self):
        # La premisa del porte, medida y no leída: mientras fuera un alias,
        # `make_alias`/`add_join` no existían y `_traverse_related_sql` no se
        # podía portar. Si esto empieza a fallar, alguien deshizo el porte.
        assert Query is not QuerySet
        assert hasattr(Query, 'make_alias') and hasattr(Query, 'add_join')


class TestFromAndWhere:
    """La forma del SQL que emite, contra la de la fuente."""

    def test_a_bare_table_needs_no_alias_clause(self):
        # _sql_from_table: si el alias ES la tabla, no emite `AS`.
        assert Query(None, 'res_partner').from_clause.code == '"res_partner"'

    def test_an_explicit_table_gets_the_as_clause(self):
        sql = Query(None, 'p', SQL.identifier('res_partner')).from_clause
        assert sql.code == '"res_partner" AS "p"'

    def test_select_defaults_to_the_id_of_the_main_table(self):
        assert Query(None, 'res_partner').select().code == \
            'SELECT "res_partner"."id" FROM "res_partner"'

    def test_where_clauses_are_joined_with_and(self):
        query = Query(None, 'res_partner')
        query.add_where(SQL("%s = %s", SQL.identifier('res_partner', 'active'), True))
        query.add_where(SQL("%s IS NOT NULL", SQL.identifier('res_partner', 'name')))
        assert query.where_clause.code == \
            '"res_partner"."active" = %s AND "res_partner"."name" IS NOT NULL'
        assert query.where_clause.params == [True]

    def test_the_main_table_is_the_first_of_the_from_clause(self):
        query = Query(None, 'res_partner')
        query.add_table('res_users')
        assert query.table == 'res_partner'


class TestJoin:
    """``make_alias`` + ``add_join`` — la superficie que el alias no tenía y
    que ``Many2one.join`` de la referencia consume."""

    def test_make_alias_composes_source_and_link(self):
        assert Query.make_alias('res_users', 'parent_id') == 'res_users__parent_id'

    def test_join_emits_the_on_condition_of_the_reference(self):
        query = Query(None, 'res_users')
        alias = query.join('res_users', 'partner_id', 'res_partner', 'id', 'partner')
        assert alias == 'res_users__partner'
        assert query.from_clause.code == (
            '"res_users" JOIN "res_partner" AS "res_users__partner" '
            'ON ("res_users"."partner_id" = "res_users__partner"."id")'
        )

    def test_left_join_differs_only_in_the_kind(self):
        query = Query(None, 'res_users')
        query.left_join('res_users', 'partner_id', 'res_partner', 'id', 'partner')
        assert 'LEFT JOIN "res_partner"' in query.from_clause.code

    def test_an_unknown_kind_of_join_is_refused(self):
        with pytest.raises(AssertionError):
            Query(None, 'res_users').add_join('CROSS JOIN', 'x', 'y', SQL("TRUE"))

    def test_the_same_join_twice_is_idempotent_not_an_error(self):
        query = Query(None, 'res_users')
        condition = SQL("%s = %s", SQL.identifier('res_users', 'partner_id'),
                        SQL.identifier('a', 'id'))
        query.add_join('JOIN', 'a', 'res_partner', condition)
        query.add_join('JOIN', 'a', 'res_partner', condition)
        assert len(query._joins) == 1

    def test_joining_from_an_unknown_alias_is_refused(self):
        with pytest.raises(AssertionError):
            Query(None, 'res_users').join('otra', 'id', 'res_partner', 'id', 'p')


class TestAliasFitsPostgres:
    """El recorte del alias — la razón por la que ``make_identifier`` salió de
    la lista de ausentes de ``tools/sql.py``."""

    def test_a_short_alias_is_left_alone(self):
        assert make_identifier('res_users__partner_id') == 'res_users__partner_id'

    def test_a_long_alias_is_truncated_and_hashed_to_63_or_less(self):
        long_link = 'a' * 80
        alias = Query.make_alias('res_partner', long_link)
        assert len(alias) == 63
        assert len(f'res_partner__{long_link}') > 63

    def test_two_long_aliases_that_share_their_prefix_do_not_collide(self):
        # Es el defecto que el recorte evita, y hay que medirlo **como lo ve
        # PostgreSQL**: comparar las cadenas enteras no discrimina —sin
        # recorte también son distintas en Python—, y el motor trunca a 63 por
        # su cuenta. Lo que importa es que sigan siendo distintas AHÍ.
        base = 'x' * 60
        first = Query.make_alias('res_partner', base + 'uno')
        second = Query.make_alias('res_partner', base + 'dos')
        assert first[:63] != second[:63]
        assert len(first) <= 63 and len(second) <= 63


class TestSubselect:
    """``subselect`` — evita el ORDER BY cuando puede y va entre paréntesis."""

    def test_subselect_wraps_in_parentheses(self):
        assert Query(None, 'res_partner').subselect().code == \
            '(SELECT "res_partner"."id" FROM "res_partner")'

    def test_a_known_empty_result_becomes_a_false_subquery(self):
        query = Query(None, 'res_partner')
        query.set_result_ids([])
        assert query.subselect().code == '(SELECT 1 WHERE FALSE)'
        assert query.is_empty()

    def test_known_ids_are_injected_instead_of_the_subquery(self):
        query = Query(None, 'res_partner')
        query.set_result_ids([3, 1, 2])
        # La divergencia de controlador declarada en tools/query.py: la
        # fuente inyecta la tupla, aquí va `unnest` de una lista porque
        # psycopg 3 no adapta la tupla a un constructor de fila.
        assert query.subselect().code == '(SELECT unnest(%s))'
        assert query.subselect().params == [[3, 1, 2]]

    def test_a_limit_forces_the_ordered_form(self):
        query = Query(None, 'res_partner')
        query.limit = 5
        assert query.subselect().code.startswith('(SELECT')
        assert 'LIMIT' in query.subselect().code


class TestSetResultIds:
    """``set_result_ids`` — con ``ordered`` la consulta respeta la secuencia."""

    def test_ordered_ids_join_against_unnest_with_ordinality(self):
        query = Query(None, 'res_partner')
        query.set_result_ids([7, 3, 9])
        code = query.select().code
        assert 'unnest' in code and 'WITH ORDINALITY' in code
        assert 'ORDER BY "res_partner__ids"."ordinality"' in code

    def test_unordered_ids_use_a_plain_in_clause(self):
        query = Query(None, 'res_partner')
        query.set_result_ids([7, 3, 9], ordered=False)
        assert '"res_partner"."id" = ANY(%s)' in query.select().code

    def test_it_refuses_a_query_that_is_no_longer_virgin(self):
        query = Query(None, 'res_partner')
        query.add_where(SQL("TRUE"))
        with pytest.raises(AssertionError):
            query.set_result_ids([1])


@pytest.mark.django_db
class TestExecution:
    """``get_result_ids``/``__len__``/``__iter__`` contra PostgreSQL real.

    Los bloques de arriba componen SQL y **nunca lo corren**: con ``env=None``
    ningún caso toca la base, así que su verde no distingue "el SELECT es
    correcto" de "el SELECT nunca se ejecutó". Este bloque cierra esa mitad —
    es el punto donde ``orm.environments.execute_query`` entra en juego.
    """

    @pytest.fixture
    def partners(self):
        Partner = apps.get_model('base', 'ResPartner')
        return [Partner.objects.create(name=f'Query {n}') for n in range(3)]

    def test_get_result_ids_returns_the_rows_of_the_table(self, partners):
        query = Query(None, ResPartner._meta.db_table)
        query.add_where(SQL(
            "%s = ANY(%s)",
            SQL.identifier(ResPartner._meta.db_table, 'id'),
            [p.pk for p in partners],
        ))
        assert set(query.get_result_ids()) == {p.pk for p in partners}

    def test_the_result_is_memoized_and_iterating_reuses_it(self, partners):
        query = Query(None, ResPartner._meta.db_table)
        query.set_result_ids([p.pk for p in partners], ordered=False)
        assert list(query) == list(query.get_result_ids())

    def test_ordered_ids_come_back_in_the_requested_order(self, partners):
        wanted = [partners[2].pk, partners[0].pk, partners[1].pk]
        query = Query(None, ResPartner._meta.db_table)
        query.set_result_ids(wanted)
        query._ids = None                      # fuerza la ida a base
        assert list(query.get_result_ids()) == wanted

    def test_len_counts_without_fetching_the_ids(self, partners):
        query = Query(None, ResPartner._meta.db_table)
        query.add_where(SQL(
            "%s = ANY(%s)",
            SQL.identifier(ResPartner._meta.db_table, 'id'),
            [p.pk for p in partners],
        ))
        assert len(query) == 3
        assert query._ids is None              # `__len__` no memoriza

    def test_a_join_resolves_against_the_real_schema(self, partners):
        # El JOIN que `Many2one.join` de la referencia emite, corrido de
        # verdad: si el alias o la condición estuvieran mal, PostgreSQL lo
        # rechazaría en vez de devolver filas.
        table = ResPartner._meta.db_table
        query = Query(None, table)
        alias = query.left_join(table, 'id', table, 'id', 'self')
        query.add_where(SQL("%s = ANY(%s)", SQL.identifier(alias, 'id'),
                            [p.pk for p in partners]))
        assert set(query.get_result_ids()) == {p.pk for p in partners}
