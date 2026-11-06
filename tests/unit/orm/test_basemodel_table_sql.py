"""Las ramas de ``BaseModel._table_sql`` que el diferencial no alcanza.

``odoo19c: odoo/orm/models.py:488-515``: con ``_table_query`` como ``SQL``
el fragmento va entre paréntesis como parámetro; como texto, entre
paréntesis en el código; sin él, el identificador de ``_table``. Si el
modelo declara ``_depends``, los campos de esa clausura viajan como
``to_flush``. El diferencial (``test_contract_model_record_reference.py``)
sólo alcanza la rama del identificador: ningún modelo de ``base`` común a
los dos árboles declara ``_table_query`` ni ``_depends``.

La propiedad se invoca por su ``fget`` sobre dobles que sólo llevan los
atributos que lee.

*Métrica:* código, parámetros y número de campos por volcar del ``SQL``.
*Ciega a:* el orden de los campos por volcar, que la fuente recorre como
pila.
"""
from orm.models import BaseModel
from tools.sql import SQL


class _Double:
    _table = 'probe_table'
    _table_query = None
    _depends = {}


def _shape(double):
    sql = BaseModel._table_sql.fget(double)
    return sql.code, tuple(sql.params), len(tuple(sql.to_flush))


def test_without_table_query_it_is_the_table_identifier():
    assert _shape(_Double()) == ('"probe_table"', (), 0)


def test_a_text_table_query_goes_inside_parentheses():
    double = _Double()
    double._table_query = 'SELECT 1 AS id'
    assert _shape(double) == ('(SELECT 1 AS id)', (), 0)


def test_an_sql_table_query_is_wrapped_as_a_parameter():
    double = _Double()
    double._table_query = SQL('SELECT %s AS id', 7)
    assert _shape(double) == ('(SELECT %s AS id)', (7,), 0)


def test_declared_depends_travel_as_fields_to_flush():
    field_a, field_b = object(), object()

    class _Other:
        _depends = {}
        _fields = {'a': field_a, 'b': field_b}

    class _Env(dict):
        pass

    double = _Double()
    double._depends = {'probe.other': ['a', 'b']}
    double.env = _Env({'probe.other': _Other()})
    code, params, flushed = _shape(double)
    assert (code, params) == ('"probe_table"', ())
    assert flushed == 2
