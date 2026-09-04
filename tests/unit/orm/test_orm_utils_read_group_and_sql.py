"""Los cuatro símbolos de ``orm/utils.py`` que la referencia declara y aquí faltaban.

``odoo19c: odoo/orm/utils.py`` declara diecisiete símbolos de nivel superior; el
censo de :ref:`analisis-censo-orm-referencia-trae-o-construye` medía cuatro
ausentes: ``READ_GROUP_TIME_GRANULARITY``, ``READ_GROUP_ALL_TIME_GRANULARITY``,
``SQL_OPERATORS`` y ``origin_ids``.

Los tres primeros son tablas: el control que discrimina no es que existan sino
que su CONTENIDO coincida con el de la fuente, clave por clave. Una tabla
declarada con la mitad de sus filas pasa un ``hasattr`` y falla en la primera
granularidad que nadie probó.
"""
import datetime
import pathlib

import dateutil.relativedelta
import pytest

import orm.utils
from orm.utils import (
    READ_GROUP_ALL_TIME_GRANULARITY,
    READ_GROUP_NUMBER_GRANULARITY,
    READ_GROUP_TIME_GRANULARITY,
    SQL_OPERATORS,
    OriginIds,
    origin_ids,
)
from tools.sql import SQL


# --- READ_GROUP_TIME_GRANULARITY -------------------------------------------

def test_time_granularity_declares_the_six_of_the_source():
    """``odoo19c: odoo/orm/utils.py:22-30`` declara exactamente estas seis."""
    assert set(READ_GROUP_TIME_GRANULARITY) == {
        'hour', 'day', 'week', 'month', 'quarter', 'year',
    }


@pytest.mark.parametrize(('clave', 'delta'), [
    ('hour', dateutil.relativedelta.relativedelta(hours=1)),
    ('day', dateutil.relativedelta.relativedelta(days=1)),
    ('week', dateutil.relativedelta.relativedelta(days=7)),
    ('month', dateutil.relativedelta.relativedelta(months=1)),
    ('quarter', dateutil.relativedelta.relativedelta(months=3)),
    ('year', dateutil.relativedelta.relativedelta(years=1)),
])
def test_each_granularity_is_the_delta_of_the_source(clave, delta):
    assert READ_GROUP_TIME_GRANULARITY[clave] == delta


def test_week_is_declared_as_seven_days_in_the_source_form():
    """La fuente declara ``days=7``; se porta esa forma, no ``weeks=1``.

    **Este control mide el TEXTO, y no por comodidad.** Medido: las dos formas
    son indistinguibles en ejecución — ``relativedelta(weeks=1)`` normaliza a
    ``relativedelta(days=+7)``, así que ``==``, ``.days`` y ``.weeks`` dan lo
    mismo para ambas. Un test de conducta sobre este eje sería un verde que no
    discrimina (sub-patrón D de ``metrica-decide-la-conclusion.md``): pasaría
    con cualquiera de las dos y no informaría de nada.

    La divergencia existe **sólo** en la forma escrita, así que ahí se mide.

    *Métrica:* el literal ``'week': dateutil.relativedelta.relativedelta(days=7)``
    en el fuente de ``orm/utils.py``.
    *Ciega a:* un reformateo que parta la línea, y a que el valor en ejecución
    sea el correcto — eso lo cubren los dos tests de arriba.
    """
    fuente = pathlib.Path(orm.utils.__file__).read_text(encoding='utf-8')
    assert "'week': dateutil.relativedelta.relativedelta(days=7)" in fuente
    assert "'week': dateutil.relativedelta.relativedelta(weeks=1)" not in fuente


def test_the_delta_actually_advances_the_date():
    base = datetime.date(2026, 1, 31)
    assert base + READ_GROUP_TIME_GRANULARITY['month'] == datetime.date(2026, 2, 28)
    assert base + READ_GROUP_TIME_GRANULARITY['quarter'] == datetime.date(2026, 4, 30)


# --- READ_GROUP_ALL_TIME_GRANULARITY ---------------------------------------

def test_all_granularity_is_the_union_of_both_tables():
    """``odoo19c: odoo/orm/utils.py:44`` — ``TIME | NUMBER``, en ese orden."""
    assert READ_GROUP_ALL_TIME_GRANULARITY == (
        READ_GROUP_TIME_GRANULARITY | READ_GROUP_NUMBER_GRANULARITY
    )
    assert len(READ_GROUP_ALL_TIME_GRANULARITY) == 16


def test_the_union_does_not_mutate_its_operands():
    """El ``|`` de dict devuelve uno nuevo; un ``update`` habría mutado.

    Sin este caso, portarlo con ``TIME.update(NUMBER)`` pasaría el test de
    igualdad de arriba y dejaría ``READ_GROUP_TIME_GRANULARITY`` con diez
    claves de más — que es lo que consume ``read_group`` al agrupar por tiempo.
    """
    assert len(READ_GROUP_TIME_GRANULARITY) == 6
    assert len(READ_GROUP_NUMBER_GRANULARITY) == 10


# --- SQL_OPERATORS ---------------------------------------------------------

def test_sql_operators_declares_the_sixteen_of_the_source():
    assert set(SQL_OPERATORS) == {
        '=', '!=', 'in', 'not in', '<', '>', '<=', '>=',
        'like', 'ilike', '=like', '=ilike',
        'not like', 'not ilike', 'not =like', 'not =ilike',
    }


@pytest.mark.parametrize(('operator', 'code'), [
    ('=', ' = '),
    ('!=', ' != '),
    ('in', ' IN '),
    ('not in', ' NOT IN '),
    ('<', ' < '),
    ('>', ' > '),
    ('<=', ' <= '),
    ('>=', ' >= '),
    ('like', ' LIKE '),
    ('ilike', ' ILIKE '),
    ('=like', ' LIKE '),
    ('=ilike', ' ILIKE '),
    ('not like', ' NOT LIKE '),
    ('not ilike', ' NOT ILIKE '),
    ('not =like', ' NOT LIKE '),
    ('not =ilike', ' NOT ILIKE '),
])
def test_each_operator_carries_the_fragment_of_the_source(operator, code):
    """Los cuatro pares ``=like``/``like`` colapsan al mismo SQL, como la fuente."""
    fragment = SQL_OPERATORS[operator]
    assert isinstance(fragment, SQL)
    assert fragment.code == code


def test_every_fragment_carries_no_parameters():
    """Son literales: si alguno trajera ``params`` sería interpolación, no un
    fragmento componible, y el `join` de quien lo use cuadraría mal."""
    assert all(f.params == [] for f in SQL_OPERATORS.values())


def test_the_fragments_compose_with_sql():
    condition = SQL('%s%s%s', SQL.identifier('name'), SQL_OPERATORS['ilike'], 'abc')
    assert ' ILIKE ' in condition.code
    assert condition.params == ['abc']


# --- origin_ids ------------------------------------------------------------

def test_origin_ids_is_the_class_not_a_copy():
    """``odoo19c: odoo/orm/utils.py:149`` — ``origin_ids = OriginIds``.

    Es el alias, no una subclase ni una función que la envuelva: quien haga
    ``isinstance(x, OriginIds)`` tras construir con ``origin_ids`` acierta.
    """
    assert origin_ids is OriginIds


def test_the_alias_builds_a_reversible_iterable():
    reales = origin_ids([1, 2, 3])
    assert list(reales) == [1, 2, 3]
    assert list(reversed(reales)) == [3, 2, 1]
