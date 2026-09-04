"""Tests de ``Base._web_read_group_fill_temporal`` — relleno de huecos
temporales en el resultado de ``formatted_read_group``.

Adaptado de ``odoo19c: addons/web/models/models.py:970-1127``. El método era
uno de los tres símbolos declinados en la cabecera de
``addons/web/models/models.py`` citando ``grep -rln "date_utils\\|def start_of"
src/tools/*.py src/orm/*.py`` → 0; hoy ``src/tools/date_utils.py`` existe con
``start_of``/``end_of``/``date_range``, así que la razón caducó y el símbolo
se porta (tarea #250).

Cada caso distingue dos comportamientos: no basta con que el método devuelva
algo, tiene que devolver una cosa y no la otra.
"""
from datetime import date, datetime

import pytest

from addons.base.models.ir_cron import IrCron
from addons.base.models.ir_sequence import IrSequenceDateRange
from addons.web.models.models import Base

#: Los tres nombres que ``formatted_read_group`` produce para un ``spec``.
_MONTH_SPEC = 'date_from:month'
_MONTH_KEY = 'gb_date_from_month'
_MONTH_MAP = {_MONTH_SPEC: _MONTH_KEY, '__count': '__count'}


def _month_row(year, month, count):
    return {_MONTH_KEY: date(year, month, 1), '__count': count}


def _fill(rows, **kwargs):
    return Base._web_read_group_fill_temporal(
        IrSequenceDateRange, rows, (_MONTH_SPEC,), _MONTH_MAP, ('__count',), **kwargs)


def test_inserts_the_missing_months_between_two_present_buckets():
    """Jun-Sep-Dic → Jun..Dic: siete meses contiguos, no tres.

    Discrimina relleno de paso a través: sin el método el resultado son las
    tres filas de entrada.
    """
    rows = [_month_row(2026, 6, 3), _month_row(2026, 9, 5), _month_row(2026, 12, 2)]

    filled = _fill(rows)

    assert [r[_MONTH_KEY] for r in filled] == [date(2026, m, 1) for m in range(6, 13)]


def test_the_inserted_bucket_carries_zero_and_not_null():
    """El hueco rellenado trae ``__count`` 0.

    Discrimina el valor vacío del agregado: un ``None`` rompe el gráfico que
    motiva el método (la barra no se dibuja), y es lo que saldría de copiar
    el ``None`` de Django sin pasar por ``_read_group_empty_value``.
    """
    filled = _fill([_month_row(2026, 6, 3), _month_row(2026, 8, 4)])

    july = next(r for r in filled if r[_MONTH_KEY] == date(2026, 7, 1))
    assert july['__count'] == 0
    assert july['__count'] is not None


def test_the_present_buckets_keep_their_aggregate():
    """Rellenar no toca las filas que ya venían.

    Discrimina relleno de reconstrucción: un método que rearmara la lista
    entera desde cero perdería los agregados medidos.
    """
    filled = _fill([_month_row(2026, 6, 3), _month_row(2026, 8, 4)])

    by_month = {r[_MONTH_KEY]: r['__count'] for r in filled}
    assert by_month[date(2026, 6, 1)] == 3
    assert by_month[date(2026, 8, 1)] == 4


def test_a_groupby_without_granularity_is_left_untouched():
    """Agrupar por un campo no temporal devuelve las filas tal cual.

    Discrimina "rellena todo agrupamiento" de "rellena sólo el temporal":
    con ``number_next`` (``IntegerField``) no hay periodo que interpolar.
    """
    rows = [{'number_next': 1, '__count': 1}, {'number_next': 9, '__count': 2}]

    filled = Base._web_read_group_fill_temporal(
        IrSequenceDateRange, rows, ('number_next',),
        {'number_next': 'number_next', '__count': '__count'}, ('__count',))

    assert filled == rows


def test_fill_from_and_fill_to_bound_the_interpolation():
    """Con cotas Ago–Oct, Jun y Dic sobreviven pero el hueco Jul no se rellena.

    Es el ejemplo documentado en la referencia (``:1013-1017``). Discrimina
    cotas honradas de cotas ignoradas: sin ellas saldrían los siete meses.
    """
    rows = [_month_row(2026, 6, 1), _month_row(2026, 9, 1), _month_row(2026, 12, 1)]

    filled = _fill(rows, fill_from='2026-08-01', fill_to='2026-10-01')

    assert [r[_MONTH_KEY] for r in filled] == [
        date(2026, 6, 1), date(2026, 8, 1), date(2026, 9, 1),
        date(2026, 10, 1), date(2026, 12, 1),
    ]


def test_min_groups_extends_past_the_last_existing_bucket():
    """Un solo grupo en Ago con ``min_groups=4`` da Ago..Nov.

    Discrimina el mínimo garantizado de "rellenar sólo entre lo existente":
    con una sola fila no hay hueco interno que rellenar.
    """
    filled = _fill([_month_row(2026, 8, 7)], min_groups=4)

    assert [r[_MONTH_KEY] for r in filled] == [date(2026, m, 1) for m in (8, 9, 10, 11)]
    assert [r['__count'] for r in filled] == [7, 0, 0, 0]


def test_the_null_bucket_survives_and_lands_last():
    """El grupo "sin fecha" no se pierde ni se interpola.

    Discrimina conservar el nulo de tragárselo: ``None`` no es un punto de la
    recta temporal, así que va al final, no entre los meses.
    """
    rows = [_month_row(2026, 6, 1), {_MONTH_KEY: None, '__count': 9}, _month_row(2026, 8, 1)]

    filled = _fill(rows)

    assert filled[-1][_MONTH_KEY] is None
    assert filled[-1]['__count'] == 9
    assert [r[_MONTH_KEY] for r in filled[:-1]] == [date(2026, m, 1) for m in (6, 7, 8)]


def test_without_rows_and_without_bounds_nothing_is_invented():
    """Sin filas ni cotas el resultado es vacío.

    Discrimina "rellena desde hoy" de "no hay de dónde partir" — la
    referencia es explícita: *no group will be returned*.
    """
    assert _fill([]) == []


def test_without_rows_the_bounds_alone_generate_the_buckets():
    """Sin filas pero con cotas, salen los meses del rango.

    Discrimina el caso anterior: la lista vacía no es un cortocircuito.
    """
    filled = _fill([], fill_from='2026-03-01', fill_to='2026-05-01')

    assert [r[_MONTH_KEY] for r in filled] == [date(2026, m, 1) for m in (3, 4, 5)]
    assert all(r['__count'] == 0 for r in filled)


def test_week_granularity_steps_seven_days_not_one_month():
    """Dos semanas separadas por una → tres cubos de lunes ISO.

    Discrimina el paso por granularidad: con el paso mensual saldrían dos
    filas. Sobre ``datetime`` (``nextcall``), que es el otro tipo temporal.
    """
    key = 'gb_nextcall_week'
    spec_map = {'nextcall:week': key, '__count': '__count'}
    rows = [
        {key: datetime(2026, 3, 2), '__count': 1},
        {key: datetime(2026, 3, 16), '__count': 4},
    ]

    filled = Base._web_read_group_fill_temporal(
        IrCron, rows, ('nextcall:week',), spec_map, ('__count',))

    assert [r[key] for r in filled] == [
        datetime(2026, 3, 2), datetime(2026, 3, 9), datetime(2026, 3, 16)]


def test_fill_temporal_with_a_limit_is_refused():
    """``formatted_read_group`` rechaza ``fill_temporal`` junto a limit/offset.

    Paridad con la referencia (``:914``): rellenar una página produciría
    grupos que la siguiente vuelve a emitir. Discrimina el rechazo de la
    aceptación silenciosa, que es el fallo que no se ve hasta el paginador.
    """
    with pytest.raises(ValueError):
        Base.formatted_read_group(
            IrSequenceDateRange.objects.none(), (_MONTH_SPEC,), ('__count',),
            limit=5, fill_temporal={})
