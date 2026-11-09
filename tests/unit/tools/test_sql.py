"""``tools.sql.SQL`` — el fragmento componible portado en la tarea #549.

Fiel a ``odoo19c: odoo/tools/sql.py:46-201`` (clase ``SQL``) y a
``odoo19c: odoo/tools/misc.py:1959-1977`` (``named_to_positional_printf``).

Lógica pura: ningún caso toca la base — la composición, los parámetros, los
identificadores y el anidamiento se verifican sobre ``code``/``params``.
La adaptación ``output_field``/``resolve_expression`` se retiró con
TASK-API-0486: ``SQL`` es la clase de la referencia y la expresión de Django
la construye su consumidor con ``RawSQL``.
"""

import warnings

import pytest
from django.db import models
from django.db.models.expressions import RawSQL

from addons.stock.models.stock_quant import StockQuant
from tools.misc import named_to_positional_printf
from tools.sql import IDENT_RE, SQL, SQL_ORDER_BY_TYPE

pytestmark = pytest.mark.unit


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
    sql = SQL(
        "%s AND %s", SQL("a", to_flush=field_a), SQL("b", to_flush=field_b)
    )
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
    assert (
        SQL.identifier("stock_quant", "quantity").code
        == '"stock_quant"."quantity"'
    )


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
    assert named_to_positional_printf(
        "%(a)s-%(b)s-%(a)s", {'a': 1, 'b': 2}
    ) == ("%s-%s-%s", (1, 2, 1))


def test_named_to_positional_printf_escapes_double_percent():
    assert named_to_positional_printf("a%%b %(x)s", {'x': 9}) == (
        "a%%b %s",
        (9,),
    )


# -- ``SQL_ORDER_BY_TYPE`` (``odoo19c: odoo/tools/sql.py:261-272``) ----------


def test_an_unknown_column_type_orders_last_and_joins_the_map():
    """El ``defaultdict(lambda: 16, ...)`` de la referencia: un tipo que no
    está en la tabla ordena con 16, y leerlo lo añade al mapa."""
    assert 'kaupamex_unknown_type' not in SQL_ORDER_BY_TYPE
    assert SQL_ORDER_BY_TYPE['kaupamex_unknown_type'] == 16
    assert 'kaupamex_unknown_type' in SQL_ORDER_BY_TYPE
    del SQL_ORDER_BY_TYPE['kaupamex_unknown_type']


# -- el consumidor Django de una expresión SQL cruda --------------------------


def test_output_field_is_an_ordinary_unused_name_as_in_the_reference():
    """``output_field`` no es parámetro de ``SQL``: llega a ``**kwargs`` y,
    como cualquier nombre que la plantilla no usa,
    ``named_to_positional_printf`` lo ignora
    (``odoo19c: odoo/tools/misc.py``). ``SQL`` no es una expresión de
    Django."""
    sql = SQL('NULL', output_field=models.DecimalField())
    assert (sql.code, sql.params) == ('NULL', [])
    assert not hasattr(sql, 'resolve_expression')


def test_stock_quant_builds_its_django_expression_with_rawsql():
    """``_read_group_select`` mezcla ``Sum`` de Django con SQL crudo; la
    expresión cruda es ``RawSQL`` con su ``output_field``."""
    expression = StockQuant._read_group_select('available_quantity:sum')
    assert isinstance(expression, RawSQL)
    assert expression.sql == 'SUM(quantity) - SUM(reserved_quantity)'
    assert isinstance(expression.output_field, models.DecimalField)
