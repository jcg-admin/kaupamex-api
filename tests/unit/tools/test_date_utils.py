"""``tools.date_utils`` — los recortes de periodo y el DSL de fecha relativa.

Adaptación de ``odoo19c: odoo/tools/date_utils.py`` (LGPL-3). Lógica pura, sin
base de datos salvo los dos casos que ejercitan el usuario activo.

Los valores esperados salen del **docstring de la fuente** (``:108-138``), que
enumera el DSL con sus ejemplos: ``"+3d"``, ``"-1m"``, ``"=1d"``, ``"=6m"``,
``"=3H"``, ``"=tuesday"``, ``"+monday"``, ``"=week_start"``. Un puerto que
cambie la semántica de cualquiera de esos ocho falla aquí.

*Métrica:* los 20 símbolos que la fuente declara, cada uno con al menos un caso
cuyo valor esperado no es el de entrada.
*Ciega a:* el comportamiento bajo un ``res.lang`` sembrado con ``week_start``
distinto de 1 — la base de pruebas no siembra idiomas, así que
``_current_week_start`` cae siempre a su respaldo. Ese camino queda cubierto
por su propio caso, que fija el respaldo, no la lectura.
"""
import datetime
import zoneinfo

import babel
import pytest
from dateutil.relativedelta import relativedelta

from tools import date_utils as du

pytestmark = pytest.mark.unit

MX = zoneinfo.ZoneInfo('America/Mexico_City')
MADRID = zoneinfo.ZoneInfo('Europe/Madrid')
A_DAY = datetime.date(2026, 8, 29)          # sábado
AN_INSTANT = datetime.datetime(2026, 8, 29, 14, 37, 21, 500000)


# -- start_of / end_of: los siete granos ------------------------------------

@pytest.mark.parametrize(('granularity', 'expected'), [
    ('year', datetime.date(2026, 1, 1)),
    ('quarter', datetime.date(2026, 7, 1)),
    ('month', datetime.date(2026, 8, 1)),
    ('week', datetime.date(2026, 8, 24)),     # lunes de esa semana
    ('day', datetime.date(2026, 8, 29)),
])
def test_start_of_truncates_the_date_to_the_granularity(granularity, expected):
    assert du.start_of(A_DAY, granularity) == expected


@pytest.mark.parametrize(('granularity', 'expected'), [
    ('year', datetime.date(2026, 12, 31)),
    ('quarter', datetime.date(2026, 9, 30)),
    ('month', datetime.date(2026, 8, 31)),
    ('week', datetime.date(2026, 8, 30)),     # domingo de esa semana
    ('day', datetime.date(2026, 8, 29)),
])
def test_end_of_extends_the_date_to_the_granularity(granularity, expected):
    assert du.end_of(A_DAY, granularity) == expected


def test_start_of_hour_keeps_the_hour_and_clears_the_rest():
    assert du.start_of(AN_INSTANT, 'hour') == datetime.datetime(2026, 8, 29, 14)


def test_end_of_hour_reaches_the_last_microsecond():
    assert du.end_of(AN_INSTANT, 'hour') == datetime.datetime(2026, 8, 29, 14, 59, 59, 999999)


def test_start_of_rejects_an_unknown_granularity():
    with pytest.raises(ValueError, match='Granularity'):
        du.start_of(A_DAY, 'fortnight')


# -- los recortes con nombre propio -----------------------------------------

def test_get_month_returns_the_first_and_the_last():
    assert du.get_month(A_DAY) == (datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))


def test_get_quarter_number_counts_from_one():
    assert du.get_quarter_number(A_DAY) == 3


def test_get_quarter_spans_the_three_months():
    assert du.get_quarter(A_DAY) == (datetime.date(2026, 7, 1), datetime.date(2026, 9, 30))


def test_get_fiscal_year_closes_in_december_by_default():
    assert du.get_fiscal_year(A_DAY) == (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))


def test_get_fiscal_year_staggered_starts_the_previous_year():
    # Cierre el 30 de junio: agosto de 2026 cae en el ejercicio 2026-07-01 → 2027-06-30.
    assert du.get_fiscal_year(A_DAY, day=30, month=6) == (
        datetime.date(2026, 7, 1), datetime.date(2027, 6, 30))


# -- aritmética -------------------------------------------------------------

def test_get_timedelta_turns_the_granularity_into_a_relativedelta():
    # El resultado se SUMA directamente. ``add`` no sirve aqui: reenvia sus
    # posicionales a ``relativedelta(*args)`` (``odoo19c: :360``), donde el
    # primero es ``dt1`` y no un delta ya construido.
    assert A_DAY + du.get_timedelta(2, 'week') == datetime.date(2026, 9, 12)
    assert A_DAY + du.get_timedelta(1, 'month') == datetime.date(2026, 9, 29)
    assert A_DAY + du.get_timedelta(-1, 'year') == datetime.date(2025, 8, 29)


def test_add_and_subtract_are_inverses():
    assert du.subtract(du.add(A_DAY, months=1), months=1) == A_DAY


def test_date_range_walks_from_start_to_end_inclusive():
    assert list(du.date_range(datetime.date(2026, 1, 1), datetime.date(2026, 4, 1))) == [
        datetime.date(2026, 1, 1), datetime.date(2026, 2, 1),
        datetime.date(2026, 3, 1), datetime.date(2026, 4, 1),
    ]


def test_date_range_rejects_a_null_step():
    with pytest.raises(ValueError, match='step is null'):
        list(du.date_range(datetime.date(2026, 1, 1), datetime.date(2026, 4, 1),
                           du.relativedelta()))


def test_date_range_rejects_start_after_end():
    with pytest.raises(ValueError, match='start > end'):
        list(du.date_range(datetime.date(2026, 4, 1), datetime.date(2026, 1, 1)))


def test_sum_intervals_adds_up_in_hours():
    morning = (datetime.datetime(2026, 1, 1, 9), datetime.datetime(2026, 1, 1, 13))
    afternoon = (datetime.datetime(2026, 1, 1, 14), datetime.datetime(2026, 1, 1, 18))
    assert du.sum_intervals([morning, afternoon]) == 8.0


# -- hora decimal -----------------------------------------------------------

def test_float_to_time_splits_the_fraction_into_minutes():
    assert du.float_to_time(9.5) == datetime.time(9, 30)


def test_float_to_time_twenty_four_is_the_last_instant():
    assert du.float_to_time(24.0) == datetime.time.max


def test_time_to_float_is_the_inverse_of_float_to_time():
    assert du.time_to_float(datetime.time(9, 30)) == 9.5


# -- husos: la adaptación de pytz a zoneinfo --------------------------------

def test_localized_attaches_utc_to_the_naive():
    assert du.localized(AN_INSTANT).tzinfo is du.utc


def test_localized_respects_the_one_that_already_has_tz():
    with_tz = AN_INSTANT.replace(tzinfo=MX)
    assert du.localized(with_tz).tzinfo is MX


def test_to_timezone_without_tz_returns_naive_utc():
    in_utc = datetime.datetime(2026, 1, 1, 12, tzinfo=du.utc)
    assert du.to_timezone(None)(in_utc) == datetime.datetime(2026, 1, 1, 12)


def test_to_timezone_converts_the_instant():
    in_utc = datetime.datetime(2026, 1, 1, 12, tzinfo=du.utc)
    assert du.to_timezone(MX)(in_utc).hour == 6      # UTC-6 en enero


def test_date_range_keeps_the_tz_of_the_start():
    # ≙ ``post_process = start.tzinfo.localize`` de la fuente, que aquí es
    # ``replace(tzinfo=...)`` porque un ``ZoneInfo`` ya es correcto por hora
    # de pared.
    output = list(du.date_range(datetime.datetime(2026, 1, 1, tzinfo=MX),
                                datetime.datetime(2026, 3, 1, tzinfo=MX)))
    assert [d.tzinfo for d in output] == [MX, MX, MX]


def test_date_range_rejects_two_different_timezones():
    # ≙ la comparación ``start.tzinfo.zone != end.tzinfo.zone``, que aquí es
    # :func:`_tz_key`.
    with pytest.raises(ValueError, match='inconsistent'):
        list(du.date_range(datetime.datetime(2026, 1, 1, tzinfo=MX),
                           datetime.datetime(2026, 3, 1, tzinfo=MADRID)))


def test_date_range_rejects_mixing_naive_with_aware():
    with pytest.raises(ValueError, match='mismatch'):
        list(du.date_range(datetime.datetime(2026, 1, 1),
                           datetime.datetime(2026, 3, 1, tzinfo=du.utc)))


def test_tz_key_reads_the_iana_key():
    assert du._tz_key(MX) == 'America/Mexico_City'


def test_tz_key_falls_back_to_str_for_a_fixed_offset():
    fixed = datetime.timezone(datetime.timedelta(hours=-6))
    assert du._tz_key(fixed) == str(fixed)


# -- semana según el idioma (babel) -----------------------------------------

def test_weeknumber_returns_year_and_week():
    assert du.weeknumber(babel.Locale.parse('es_MX'), A_DAY) == (2026, 35)


def test_weekstart_goes_back_to_the_first_day_of_the_week():
    assert du.weekstart(babel.Locale.parse('es_MX'), A_DAY) == datetime.date(2026, 8, 23)


def test_weekend_moves_to_the_last_day_of_the_week():
    assert du.weekend(babel.Locale.parse('es_MX'), A_DAY) == datetime.date(2026, 8, 29)


# -- parse_iso_date ---------------------------------------------------------

def test_parse_iso_date_short_returns_date():
    assert du.parse_iso_date('2026-08-29') == A_DAY


def test_parse_iso_date_long_returns_datetime():
    assert du.parse_iso_date('2026-08-29T14:37:21') == datetime.datetime(2026, 8, 29, 14, 37, 21)


def test_parse_iso_date_rejects_an_explicit_timezone():
    with pytest.raises(ValueError, match='no timezone'):
        du.parse_iso_date('2026-08-29T14:37:21+00:00')


# -- parse_date: los ocho ejemplos del docstring de la fuente ---------------

def test_parse_date_delegates_to_iso_when_it_starts_with_digits():
    assert du.parse_date('2026-08-29') == A_DAY


def test_parse_date_rejects_the_empty_string():
    with pytest.raises(ValueError, match='Empty date'):
        du.parse_date('   ')


def test_parse_date_rejects_a_term_without_operator():
    with pytest.raises(ValueError, match='Invalid term'):
        du.parse_date('today 3d')


def test_parse_date_today_returns_date_and_now_returns_datetime():
    assert isinstance(du.parse_date('today'), datetime.date)
    assert isinstance(du.parse_date('now'), datetime.datetime)


def test_parse_date_adds_three_days():
    # "+3d" del docstring de la fuente.
    assert du.parse_date('today +3d') - du.parse_date('today') == datetime.timedelta(days=3)


def test_parse_date_subtracts_one_month():
    # "-1m" del docstring de la fuente.
    today = du.parse_date('today')
    assert du.parse_date('today -1m') == today - du.relativedelta(months=1)


def test_parse_date_pins_the_first_day_of_the_month():
    # "=1d" del docstring: fija el día 1.
    assert du.parse_date('today =1d').day == 1


def test_parse_date_pins_june():
    # "=6m" del docstring: fija el mes 6 y reinicia lo menor. "Lo menor" es la
    # HORA, no el dia: la rama de fijado aplica ``TRUNCATE_UNIT['month']``, que
    # es ``TRUNCATE_TODAY`` — microsegundo, segundo, minuto y hora a cero
    # (``odoo19c: :22-31,:82-85``). El dia del mes sobrevive, **si cabe** en el
    # mes fijado; ver el caso siguiente.
    hoy = du.parse_date('today')
    pinned = du.parse_date('today =6m')
    assert (pinned.month, pinned.day) == (6, min(hoy.day, 30))
    pinned_with_time = du.parse_date('now =6m')
    assert pinned_with_time.month == 6
    assert (pinned_with_time.hour, pinned_with_time.minute,
            pinned_with_time.second, pinned_with_time.microsecond) == (0, 0, 0, 0)


def test_pinning_a_month_clamps_a_day_that_does_not_fit():
    """El 31 fijado a un mes de 30 dias cae al 30, no al 1 del siguiente.

    Es el comportamiento documentado de ``relativedelta``, que la fuente hereda
    sin envolverlo: ``date(2026, 8, 31) + relativedelta(month=6)`` da el 30 de
    junio. No hay codigo nuestro que lo decida — el caso existe para que la
    conducta quede fijada y no se re-descubra.

    **Este caso nacio de un rojo del calendario.** El anterior afirmaba que el
    dia del mes sobrevive *siempre* al fijado, y con eso pasaba los 28 primeros
    dias de cada mes y fallaba el 31 de agosto: su verde no distinguia *"el dia
    sobrevive"* de *"hoy es un dia que cabe en junio"*. Por eso los dos miden
    ahora contra fechas **fijadas** y no contra el dia en que corren.
    """
    agosto_31 = datetime.date(2026, 8, 31)
    assert agosto_31 + relativedelta(month=6) == datetime.date(2026, 6, 30)
    assert agosto_31 + relativedelta(month=2) == datetime.date(2026, 2, 28)
    # uno que si cabe, como control positivo: sin el, el caso pasaria igual si
    # el recorte se aplicara a todos los dias por igual
    assert datetime.date(2026, 8, 15) + relativedelta(month=6) == \
        datetime.date(2026, 6, 15)


def test_parse_date_pins_three_in_the_morning():
    # "=3H" del docstring: fija la hora y reinicia minutos y segundos.
    pinned = du.parse_date('now =3H')
    assert (pinned.hour, pinned.minute, pinned.second, pinned.microsecond) == (3, 0, 0, 0)


def test_parse_date_pins_tuesday_of_the_week():
    # "=tuesday" del docstring.
    assert du.parse_date('today =tuesday').weekday() == 1


def test_parse_date_moves_to_next_monday_without_going_back():
    # "+monday" del docstring: no cambia si ya es lunes.
    next_one = du.parse_date('today +monday')
    assert next_one.weekday() == 0
    assert next_one >= du.parse_date('today')


def test_parse_date_goes_back_to_the_previous_monday():
    previous_one = du.parse_date('today -monday')
    assert previous_one.weekday() == 0
    assert previous_one <= du.parse_date('today')


def test_parse_date_week_start_uses_the_monday_fallback():
    # "=week_start" del docstring. Sin ``res.lang`` sembrado,
    # ``_current_week_start`` devuelve 1 (lunes) — su respaldo declarado.
    assert du._current_week_start() == 1
    assert du.parse_date('today =week_start').weekday() == 0


def test_parse_date_chains_several_terms():
    assert du.parse_date('today =1d +1m') == du.parse_date('today =1d') + du.relativedelta(months=1)


# -- el usuario activo, que es la divergencia de firma ----------------------

def test_current_timezone_falls_back_to_utc_without_an_active_user():
    # La firma de la fuente recibe ``env``; aquí el usuario sale de
    # ``orm.environments.get_current_user()``, que sin petición devuelve None.
    assert du._current_timezone() is du.utc
