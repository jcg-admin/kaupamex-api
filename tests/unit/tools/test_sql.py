"""``tools.sql.SQL`` — el fragmento componible portado en la tarea #549.

Fiel a ``odoo19c: odoo/tools/sql.py:46-201`` (clase ``SQL``) y a
``odoo19c: odoo/tools/misc.py:1959-1977`` (``named_to_positional_printf``).

Lógica pura: ningún caso toca la base — la composición, los parámetros, los
identificadores y el anidamiento se verifican sobre ``code``/``params``. La
retrocompatibilidad con el alias retirado (``SQL = RawSQL``) se fija en la
sección de ``output_field``/``resolve_expression``: es el contrato que
``addons/stock/models/stock_quant.py:831,834`` consume sin editarse
(H-API-698).
"""
import warnings

import pytest
from django.db import models
from django.db.models.expressions import RawSQL

from tools.misc import named_to_positional_printf
from tools.sql import IDENT_RE, SQL

pytestmark = pytest.mark.unit


class _QueryStub:
    """Sustituto mínimo del ``Query`` de Django para ``resolve_expression``.

    ``RawSQL.resolve_expression`` sólo consulta ``query.model``; con ``None``
    cae al camino genérico de ``Expression`` sin tocar la base.
    """
    model = None


# -- construcción básica (``odoo19c: odoo/tools/sql.py:89-135``) --------------

def test_empty_sql_has_empty_code_and_params():
    sql = SQL()
    assert sql.code == ''
    assert sql.params == []


def test_plain_code_without_parameters():
    sql = SQL("SELECT 1")
    assert sql.code == 'SELECT 1'
    assert sql.params == []


def test_positional_parameters_stay_as_placeholders():
    sql = SQL("UPDATE foo SET a = %s, b = %s", 'hello', 42)
    assert sql.code == 'UPDATE foo SET a = %s, b = %s'
    assert sql.params == ['hello', 42]


def test_named_parameters_become_positional():
    """La interpolación por nombre — lo que el alias ``RawSQL`` no tenía."""
    sql = SQL("a = %(x)s AND b = %(y)s AND c = %(x)s", x=1, y='q')
    assert sql.code == 'a = %s AND b = %s AND c = %s'
    assert sql.params == [1, 'q', 1]


def test_code_without_args_must_escape_percent():
    """``%`` literal siempre va como ``%%`` — un ``%s`` suelto es TypeError."""
    assert SQL("foo LIKE 'a%%'").code == "foo LIKE 'a%%'"
    with pytest.raises(TypeError):
        SQL("a = %s")


def test_positional_and_named_arguments_are_mutually_exclusive():
    with pytest.raises(TypeError):
        SQL("%s %(x)s", 1, x=2)


# -- composición y anidamiento (``odoo19c: odoo/tools/sql.py:116-135``) -------

def test_nested_sql_objects_merge_code_and_params():
    sql = SQL(
        "UPDATE %s SET %s",
        SQL.identifier("foo"),
        SQL("%s = %s", SQL.identifier("bar"), 42),
    )
    assert sql.code == 'UPDATE "foo" SET "bar" = %s'
    assert sql.params == [42]


def test_literal_percent_survives_composition():
    sql = SQL("x LIKE 'a%%' AND y = %s", 7)
    assert sql.code == "x LIKE 'a%%' AND y = %s"
    assert sql.params == [7]


def test_copy_constructor_from_sql_rejects_extra_arguments():
    original = SQL("a = %s", 5)
    copia = SQL(original)
    assert copia == original
    with pytest.raises(TypeError):
        SQL(original, 1)
    with pytest.raises(TypeError):
        SQL(original, x=1)


def test_to_flush_collects_the_metadata_of_all_parts():
    field_a, field_b = object(), object()
    sql = SQL("%s AND %s", SQL("a", to_flush=field_a), SQL("b", to_flush=field_b))
    assert tuple(sql.to_flush) == (field_a, field_b)


def test_to_flush_accepts_a_single_field_or_an_iterable():
    field = object()
    assert tuple(SQL("a", to_flush=field).to_flush) == (field,)
    assert tuple(SQL("a", to_flush=[field]).to_flush) == (field,)


# -- join (``odoo19c: odoo/tools/sql.py:178-192``) ----------------------------

def test_join_with_a_parameterless_separator():
    joined = SQL(", ").join([SQL.identifier("a"), SQL.identifier("b"), 3])
    assert joined.code == '"a", "b", %s'
    assert joined.params == [3]


def test_join_with_a_parameterized_separator_alternates_items():
    joined = SQL(" %s ", 0).join([1, 2])
    assert joined.code == '%s %s %s'
    assert joined.params == [1, 0, 2]


def test_join_of_an_empty_iterable_is_the_empty_sql():
    assert SQL(", ").join([]).code == ''


def test_join_of_a_single_sql_returns_it_unchanged():
    only = SQL("x")
    assert SQL(", ").join([only]) is only


# -- identifier (``odoo19c: odoo/tools/sql.py:194-201``) ----------------------

def test_identifier_quotes_the_name():
    assert SQL.identifier("stock_quant").code == '"stock_quant"'


def test_identifier_with_subname_quotes_both():
    assert SQL.identifier("stock_quant", "quantity").code == '"stock_quant"."quantity"'


def test_identifier_rejects_an_injection_attempt():
    with pytest.raises(AssertionError):
        SQL.identifier('foo"; DROP TABLE bar; --')
    with pytest.raises(AssertionError):
        SQL.identifier('foo', 'bar"')


def test_ident_re_admits_dollar_and_hyphen():
    """``IDENT_RE`` (``odoo19c: :35``) es más laxo que ``isidentifier()``."""
    assert IDENT_RE.match('col$1-x')
    assert SQL.identifier('col$1-x').code == '"col$1-x"'


# -- dunders (``odoo19c: odoo/tools/sql.py:154-176``) -------------------------

def test_equality_and_hash_cover_code_and_params():
    assert SQL("a = %s", 1) == SQL("a = %s", 1)
    assert SQL("a = %s", 1) != SQL("a = %s", 2)
    assert SQL("a") != "a"
    assert hash(SQL("a = %s", 1)) == hash(SQL("a = %s", 1))


def test_bool_reflects_the_code():
    assert not SQL()
    assert SQL("x")


def test_repr_shows_code_and_params():
    assert repr(SQL("a = %s", 5)) == "SQL('a = %s', 5)"


def test_iteration_is_deprecated_but_still_deconstructs():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        code, params = SQL("a = %s", 5)
    assert code == 'a = %s'
    assert params == [5]
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


# -- named_to_positional_printf (``odoo19c: odoo/tools/misc.py:1959``) --------

def test_named_to_positional_printf_preserves_consumption_order():
    assert named_to_positional_printf("%(a)s-%(b)s-%(a)s", {'a': 1, 'b': 2}) == \
        ("%s-%s-%s", (1, 2, 1))


def test_named_to_positional_printf_escapes_double_percent():
    assert named_to_positional_printf("a%%b %(x)s", {'x': 9}) == ("a%%b %s", (9,))


# -- retrocompatibilidad con el alias RawSQL retirado (H-API-698) -------------

def test_output_field_keyword_matches_the_stock_quant_call():
    """La llamada exacta de ``stock_quant.py:831`` construye sin error."""
    sql = SQL('NULL', output_field=models.DecimalField())
    assert sql.code == 'NULL'
    assert sql.params == []


def test_resolve_expression_delegates_to_rawsql_with_the_output_field():
    sql = SQL('SUM(quantity) - SUM(reserved_quantity)',
              output_field=models.DecimalField(max_digits=16, decimal_places=2))
    resolved = sql.resolve_expression(
        query=_QueryStub(), allow_joins=True, reuse=None, summarize=False,
        for_save=False)
    assert isinstance(resolved, RawSQL)
    assert resolved.sql == 'SUM(quantity) - SUM(reserved_quantity)'
    assert resolved.params == ()
    assert isinstance(resolved.output_field, models.DecimalField)


def test_the_copy_constructor_preserves_the_output_field():
    original = SQL('NULL', output_field=models.DecimalField())
    resolved = SQL(original).resolve_expression(query=_QueryStub())
    assert isinstance(resolved.output_field, models.DecimalField)
