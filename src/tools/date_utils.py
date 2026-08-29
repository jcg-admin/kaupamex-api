"""Aritmética de fechas — adaptación de ``odoo19c: odoo/tools/date_utils.py``
(``odoo-tools@622ddc2a``, LGPL-3 según su ``__manifest__.py`` raíz: copia +
adaptación con atribución preservada, DEC-KX-03).

Qué resuelve: los recortes de periodo (inicio y fin de año, trimestre, mes,
semana, día y hora), el rango fiscal, el generador de rangos con paso, la
conversión entre horas decimales y ``time``, y el parseo de la fecha relativa
que la barra de búsqueda escribe (``+3d``, ``=1m``, ``=monday``).

**Se portan 20 de 20 símbolos.** El archivo aterriza en ``src/tools/`` porque
``src/tools`` ↔ ``odoo/tools`` es una raíz espejada
(``atributos-de-clase-de-modelo.md``, segunda cláusula): el hogar del símbolo
lo fija la referencia, no la conveniencia del primer consumidor.

Por qué entra ahora
===================

``ResCurrency._get_simple_currency_table`` —la pieza que desbloquea las dos
vistas SQL de reporte, ``account.invoice.report`` y ``sale.report``— llama a
``date_utils.start_of(fecha, 'year')`` desde su constructor de tasa promedio
(``odoo19c: addons/account/models/res_currency.py:221``). Portar sólo
``start_of`` habría dejado un archivo parcial en una raíz espejada, que es lo
que ``porte-completo-no-parcial.md`` prohíbe.

Divergencias de mecanismo declaradas — dos
==========================================

1. ``zoneinfo`` en lugar de ``pytz``
-------------------------------------

La fuente construye sus husos con ``pytz`` (``odoo19c: :9,20``). Aquí se usan
:class:`~zoneinfo.ZoneInfo` y ``datetime.timezone.utc`` de la biblioteca
estándar, porque **Django 6 abandonó ``pytz``**: su propio
``django.utils.timezone`` resuelve por ``zoneinfo``, que lee la misma base de
datos IANA. Los cuatro archivos de ``src/addons/base/models/`` que ya tocan
husos —``ir_actions``, ``ir_cron``, ``res_users``, ``res_partner``— importan
``ZoneInfo``, así que la sustitución sigue la convención del árbol, no la
inventa.

**Corregido 2026-08-29.** Esta razón decía *«porque ``pytz`` no está instalado
ni declarado en este árbol»*, y dejó de ser cierta en el porte de
``tools/safe_eval``: la fuente expone ``pytz`` a toda expresión almacenada
(``safe_eval.py:498``), así que sin la dependencia ese porte no cierra, y
``pyproject.toml`` la declara. **La decisión no cambia** —los husos siguen
resolviéndose con ``zoneinfo``— pero su razón sí: no es que la biblioteca
falte, es que no es el mecanismo de este stack. Una razón caducada se lee como
medida y bloquea a quien la relea.

*Métrica:* ``grep -rn "import pytz\\|from zoneinfo" src/ addons/`` — el único
consumidor de ``pytz`` es ``tools/safe_eval``, que lo envuelve para las
expresiones; 4 archivos con ``zoneinfo``.
*Ciega a:* un consumidor futuro que importe ``date_utils.utc`` esperando la
interfaz de ``pytz`` (``localize``/``normalize``/``zone``). Los tres puntos
donde la fuente la usa están adaptados y anotados; un quinto uso nuevo tendría
que descubrirlo quien lo escriba.

Las tres adaptaciones, una por cada método que ``pytz`` tiene y ``zoneinfo``
no necesita:

- ``utc.localize(dt)`` (``:203`` de la fuente) → ``datetime.now(utc)``. Un
  ``tzinfo`` de ``zoneinfo`` es correcto por hora de pared, así que no hace
  falta el paso de localización que ``pytz`` exige por diseño.
- ``start.tzinfo.localize`` en ``date_range`` (``:399``) →
  ``dt.replace(tzinfo=zona)``, por la misma razón.
- ``start.tzinfo.zone`` (``:390``) → :func:`_tz_key`, que lee ``key`` de un
  ``ZoneInfo`` y cae a ``str`` para un huso de desplazamiento fijo.

2. La firma de ``parse_date``
------------------------------

La fuente declara ``parse_date(value, env)`` y consume del ``env`` cuatro
cosas: la hora actual (``Datetime.now``), el día de hoy en la zona del usuario
(``Date.context_today``), esa misma hora localizada
(``Datetime.context_timestamp``) y el primer día de semana del idioma del
usuario (``env['res.lang']._get_data(code=env.user.lang).week_start``).

Este stack **no tiene un objeto ``Environment``** que se pase por parámetro: el
usuario y la empresa activos viven en el contexto de la petición y se leen con
``orm.environments.get_current_user()`` — el hogar espejado de
``odoo/orm/environments.py``. Por eso la firma aquí es ``parse_date(value)`` y
las cuatro lecturas salen de ese accesor.

Lo que **no** cambia: el DSL entero (los tres operadores ``+ - =``, las siete
unidades de ``_SHORT_DATE_UNIT``, los siete nombres de día, ``week_start``, el
truncado por unidad y la normalización final a naive) va verbatim. La
divergencia es de **quién provee el contexto**, no de qué hace la función.

Las tres funciones de ``babel`` (``weeknumber``, ``weekstart``, ``weekend``)
se portan tal cual: reciben el ``Locale`` por parámetro, así que no tocan el
entorno.
"""
from __future__ import annotations

import calendar
import math
import re
import typing
from datetime import date, datetime, time, timedelta, tzinfo
from datetime import timezone as _timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.relativedelta import relativedelta, weekdays

from .float_utils import float_round

from django.apps import apps

from orm.environments import get_current_user

if typing.TYPE_CHECKING:
    import babel
    from collections.abc import Callable, Iterable, Iterator
    D = typing.TypeVar('D', date, datetime)

#: ≙ ``utc = pytz.utc`` (``odoo19c: :20``). Aquí es el singleton de la
#: biblioteca estándar: ``zoneinfo`` sustituye a ``pytz`` en este árbol.
utc = _timezone.utc

TRUNCATE_TODAY = relativedelta(microsecond=0, second=0, minute=0, hour=0)
TRUNCATE_UNIT = {
    'day': TRUNCATE_TODAY,
    'month': TRUNCATE_TODAY,
    'year': TRUNCATE_TODAY,
    'week': TRUNCATE_TODAY,
    'hour': relativedelta(microsecond=0, second=0, minute=0),
    'minute': relativedelta(microsecond=0, second=0),
    'second': relativedelta(microsecond=0),
}
WEEKDAY_NUMBER = dict(zip(
    ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'),
    range(7),
    strict=True,
))
_SHORT_DATE_UNIT = {
    'd': 'days',
    'm': 'months',
    'y': 'years',
    'w': 'weeks',
    'H': 'hours',
    'M': 'minutes',
    'S': 'seconds',
}

__all__ = [
    'date_range',
    'float_to_time',
    'get_fiscal_year',
    'get_month',
    'get_quarter',
    'get_quarter_number',
    'get_timedelta',
    'localized',
    'parse_date',
    'parse_iso_date',
    'sum_intervals',
    'time_to_float',
    'to_timezone',
]


def float_to_time(hours: float) -> time:
    """Convierte un número de horas en un objeto ``time``."""
    if hours == 24.0:
        return time.max
    fractional, integral = math.modf(hours)
    return time(int(integral), int(float_round(60 * fractional, precision_digits=0)), 0)


def time_to_float(duration: time | timedelta) -> float:
    """Convierte un ``time`` (o un ``timedelta``) a un número de horas."""
    if isinstance(duration, timedelta):
        return duration.total_seconds() / 3600
    if duration == time.max:
        return 24.0
    seconds = duration.microsecond / 1_000_000 + duration.second + duration.minute * 60
    return seconds / 3600 + duration.hour


def localized(dt: datetime) -> datetime:
    """Añade ``tzinfo`` (UTC) al ``datetime`` que no lo trae."""
    return dt if dt.tzinfo else dt.replace(tzinfo=utc)


def to_timezone(tz: tzinfo | None) -> Callable[[datetime], datetime]:
    """Devuelve la función que convierte un ``datetime`` a la zona dada.

    Sin zona, la función devuelve el instante en UTC y **sin** ``tzinfo`` —
    la forma naive con que este árbol persiste las fechas.
    """
    if tz is None:
        return lambda dt: dt.astimezone(utc).replace(tzinfo=None)
    return lambda dt: dt.astimezone(tz)


def parse_iso_date(value: str) -> date | datetime:
    """Parsea una cadena ISO a ``date`` o ``datetime``.

    :raises ValueError: si el formato es inválido o trae zona horaria.
    """
    # Tiene pinta de formato ISO
    if len(value) <= 10:
        return date.fromisoformat(value)
    now = datetime.fromisoformat(value)
    if now.tzinfo is not None:
        raise ValueError(f"expecting only datetimes with no timezone: {value!r}")
    return now


def _tz_key(tz: tzinfo) -> str:
    """El nombre IANA de la zona, para comparar dos husos por identidad.

    ≙ el atributo ``tzinfo.zone`` que ``date_range`` lee de la fuente
    (``odoo19c: :390``). Ese atributo es de ``pytz``; :class:`~zoneinfo.ZoneInfo`
    expone el mismo dato en ``key``, y un ``datetime.timezone`` de desplazamiento
    fijo no expone ninguno de los dos — de ahí el respaldo por ``str``.
    """
    return getattr(tz, 'key', None) or str(tz)


def _current_timezone() -> tzinfo:
    """La zona horaria del usuario activo, con UTC de respaldo.

    ≙ lo que la fuente obtiene de ``env.user.tz`` dentro de
    ``Datetime.context_timestamp`` (``odoo19c: odoo/orm/fields_temporal.py``).
    Aquí el usuario activo lo entrega ``orm.environments``, que es el hogar
    espejado de ``odoo/orm/environments.py``.
    """
    user = get_current_user()
    name = getattr(getattr(user, 'partner', None), 'tz', None) if user else None
    if not name:
        return utc
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return utc


def _current_week_start() -> int:
    """El primer día de semana del idioma del usuario, 1-indexado como la fuente.

    ≙ ``env['res.lang']._get_data(code=env.user.lang).week_start``
    (``odoo19c: odoo/tools/date_utils.py:169``). Devuelve ``1`` (lunes) cuando
    el usuario no declara idioma o el idioma no está sembrado — el mismo valor
    con que la referencia siembra ``week_start`` por omisión.
    """
    user = get_current_user()
    code = getattr(getattr(user, 'partner', None), 'lang', None) if user else None
    if code:
        res_lang = apps.get_model('base', 'ResLang')
        lang = res_lang.objects.filter(code=code).first()
        if lang is not None and lang.week_start:
            return int(lang.week_start)
    return 1


def parse_date(value: str) -> date | datetime:
    r"""Parsea una fecha técnica —ISO o relativa— a ``date`` o ``datetime``.

    Admite ISO y fechas relativas a ahora. Si la entrada empieza con
    ``r'\d+-'`` se delega en :func:`parse_iso_date`. Si no, se parte de ahora
    en la zona del usuario. También se puede partir de ``today`` (y entonces
    el resultado es ``date``). Sobre esa base se aplican desplazamientos:

    - se suma o resta ``d``, ``w``, ``m``, ``y``, ``H``, ``M``, ``S``:
      días, semanas, meses, años, horas, minutos, segundos

      - ``"+3d"`` suma tres días
      - ``"-1m"`` resta un mes

    - se fija una parte de la fecha, que reinicia a medianoche o sólo las
      partes menores

      - ``"=1d"`` fija el primer día del mes a medianoche
      - ``"=6m"`` fija junio y reinicia a medianoche
      - ``"=3H"`` fija la hora a las 3:00:00

    - los días de la semana se manejan igual

      - ``"=tuesday"`` fija el martes de esta semana a medianoche
      - ``"+monday"`` avanza al lunes siguiente (sin cambio si hoy es lunes)
      - ``"=week_start"`` fija el primer día de la semana según el idioma

    El DSL de la fecha relativa es::

        relative_date := ('today' | 'now')? offset*
        offset := date_rel | time_rel | weekday
        date_rel := (regex) [=+-]\d+[dwmy]
        time_rel := (regex) [=+-]\d+[HMS]
        weekday := [=+-] ('monday' | ... | 'sunday' | 'week_start')

    La función equivalente en JavaScript es ``parseSmartDateInput``.

    :param value: la cadena a parsear.

    **Divergencia de firma declarada:** la fuente recibe ``env`` y de él saca
    la zona y el idioma; aquí los entrega ``orm.environments``. Ver el
    docstring del módulo.
    """
    if re.match(r'\d+-', value):
        return parse_iso_date(value)
    terms = value.split()
    if not terms:
        raise ValueError("Empty date value")

    # Punto de partida
    tz = _current_timezone()
    now = datetime.now(utc).astimezone(tz)

    dt: datetime | date
    term = terms.pop(0) if terms[0] in ('today', 'now') else 'now'
    dt = now.date() if term == 'today' else now

    for term in terms:
        operator = term[0]
        if operator not in ('+', '-', '=') or len(term) < 3:
            raise ValueError(f"Invalid term {term!r} in expression date: {value!r}")

        # Día de la semana
        dayname = term[1:]
        if dayname in WEEKDAY_NUMBER or dayname == "week_start":
            week_start = _current_week_start() - 1
            weekday = week_start if dayname == "week_start" else WEEKDAY_NUMBER[dayname]
            weekday_offset = ((weekday - week_start) % 7) - ((dt.weekday() - week_start) % 7)
            if operator in ('+', '-'):
                if operator == '+' and weekday_offset < 0:
                    weekday_offset += 7
                elif operator == '-' and weekday_offset > 0:
                    weekday_offset -= 7
            elif isinstance(dt, datetime):
                dt += TRUNCATE_TODAY
            dt += timedelta(weekday_offset)
            continue

        # Operaciones sobre fechas
        try:
            unit = _SHORT_DATE_UNIT[term[-1]]
            if operator in ('+', '-'):
                number = int(term[:-1])  # con signo
            else:
                number = int(term[1:-1])
                unit = unit.removesuffix('s')
                if isinstance(dt, datetime):
                    dt += TRUNCATE_UNIT[unit]
                # ojo: '=Nw' no está soportado
            dt += relativedelta(**{unit: number})
        except (ValueError, TypeError, KeyError):
            raise ValueError(f"Invalid term {term!r} in expression date: {value!r}")

    # Siempre se devuelve una fecha naive
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        dt = dt.astimezone(utc).replace(tzinfo=None)
    return dt


def get_month(date: D) -> tuple[D, D]:
    """El rango del mes de una fecha (primer y último día)."""
    return date.replace(day=1), date.replace(day=calendar.monthrange(date.year, date.month)[1])


def get_quarter_number(date: date) -> int:
    """El trimestre de una fecha (1-4)."""
    return (date.month - 1) // 3 + 1


def get_quarter(date: D) -> tuple[D, D]:
    """El rango del trimestre de una fecha (primer y último día)."""
    month_from = (date.month - 1) // 3 * 3 + 1
    date_from = date.replace(month=month_from, day=1)
    date_to = date_from.replace(month=month_from + 2)
    date_to = date_to.replace(day=calendar.monthrange(date_to.year, date_to.month)[1])
    return date_from, date_to


def get_fiscal_year(date: D, day: int = 31, month: int = 12) -> tuple[D, D]:
    """El rango del ejercicio fiscal de una fecha (primer y último día).

    Un ejercicio fiscal es el periodo que cada gobierno usa para efectos
    contables, y varía por país. Llamada con un solo parámetro devuelve el año
    natural, porque el cierre por omisión es el ``YYYY-12-31``.

    :param date: una fecha que pertenece al ejercicio.
    :param day: el día del mes en que cierra el ejercicio.
    :param month: el mes del año en que cierra el ejercicio.
    :return: las fechas de inicio y de cierre del ejercicio.
    """

    def fix_day(year, month, day):
        max_day = calendar.monthrange(year, month)[1]
        if month == 2 and day in (28, max_day):
            return max_day
        return min(day, max_day)

    date_to = date.replace(month=month, day=fix_day(date.year, month, day))

    if date <= date_to:
        date_from = date_to - relativedelta(years=1)
        day = fix_day(date_from.year, date_from.month, date_from.day)
        date_from = date_from.replace(day=day)
        date_from += relativedelta(days=1)
    else:
        date_from = date_to + relativedelta(days=1)
        date_to = date_to + relativedelta(years=1)
        day = fix_day(date_to.year, date_to.month, date_to.day)
        date_to = date_to.replace(day=day)
    return date_from, date_to


def get_timedelta(qty: int, granularity: typing.Literal['hour', 'day', 'week', 'month', 'year']):
    """El ``relativedelta`` de la cantidad y la unidad dadas."""
    switch = {
        'hour': relativedelta(hours=qty),
        'day': relativedelta(days=qty),
        'week': relativedelta(weeks=qty),
        'month': relativedelta(months=qty),
        'year': relativedelta(years=qty),
    }
    return switch[granularity]


Granularity = typing.Literal['year', 'quarter', 'month', 'week', 'day', 'hour']


def start_of(value: D, granularity: Granularity) -> D:
    """El inicio del periodo que contiene a la fecha dada.

    :param value: fecha o ``datetime`` inicial.
    :param granularity: el tipo de periodo — ``year``, ``quarter``, ``month``,
        ``week``, ``day`` u ``hour``.
    :return: la fecha o ``datetime`` del inicio de ese periodo.
    """
    is_datetime = isinstance(value, datetime)
    if granularity == "year":
        result = value.replace(month=1, day=1)
    elif granularity == "quarter":
        # Q1 = 1 ene · Q2 = 1 abr · Q3 = 1 jul · Q4 = 1 oct
        result = get_quarter(value)[0]
    elif granularity == "month":
        result = value.replace(day=1)
    elif granularity == 'week':
        # ``calendar.weekday`` toma ISO 8601 como referencia del inicio de
        # semana: el lunes es el primer día y el domingo el último.
        result = value - relativedelta(days=calendar.weekday(value.year, value.month, value.day))
    elif granularity == "day":
        result = value
    elif granularity == "hour" and is_datetime:
        return datetime.combine(value, time.min).replace(hour=value.hour)
    elif is_datetime:
        raise ValueError(
            "Granularity must be year, quarter, month, week, day or hour for value %s" % value
        )
    else:
        raise ValueError(
            "Granularity must be year, quarter, month, week or day for value %s" % value
        )

    return datetime.combine(result, time.min) if is_datetime else result


def end_of(value: D, granularity: Granularity) -> D:
    """El fin del periodo que contiene a la fecha dada.

    :param value: fecha o ``datetime`` inicial.
    :param granularity: el tipo de periodo — ``year``, ``quarter``, ``month``,
        ``week``, ``day`` u ``hour``.
    :return: la fecha o ``datetime`` del cierre de ese periodo.
    """
    is_datetime = isinstance(value, datetime)
    if granularity == "year":
        result = value.replace(month=12, day=31)
    elif granularity == "quarter":
        # Q1 = 31 mar · Q2 = 30 jun · Q3 = 30 sep · Q4 = 31 dic
        result = get_quarter(value)[1]
    elif granularity == "month":
        result = value + relativedelta(day=1, months=1, days=-1)
    elif granularity == 'week':
        # Misma referencia ISO 8601 que ``start_of``.
        result = value + relativedelta(days=6 - calendar.weekday(value.year, value.month, value.day))
    elif granularity == "day":
        result = value
    elif granularity == "hour" and is_datetime:
        return datetime.combine(value, time.max).replace(hour=value.hour)
    elif is_datetime:
        raise ValueError(
            "Granularity must be year, quarter, month, week, day or hour for value %s" % value
        )
    else:
        raise ValueError(
            "Granularity must be year, quarter, month, week or day for value %s" % value
        )

    return datetime.combine(result, time.max) if is_datetime else result


def add(value: D, *args, **kwargs) -> D:
    """La suma de ``value`` y un :class:`relativedelta`.

    :param value: fecha o ``datetime`` inicial.
    :param args: posicionales que se pasan tal cual a :class:`relativedelta`.
    :param kwargs: nombrados que se pasan tal cual a :class:`relativedelta`.
    :return: la fecha o ``datetime`` resultante.
    """
    return value + relativedelta(*args, **kwargs)


def subtract(value: D, *args, **kwargs) -> D:
    """La diferencia entre ``value`` y un :class:`relativedelta`.

    :param value: fecha o ``datetime`` inicial.
    :param args: posicionales que se pasan tal cual a :class:`relativedelta`.
    :param kwargs: nombrados que se pasan tal cual a :class:`relativedelta`.
    :return: la fecha o ``datetime`` resultante.
    """
    return value - relativedelta(*args, **kwargs)


def date_range(start: D, end: D, step: relativedelta = relativedelta(months=1)) -> Iterator[datetime]:
    """Generador de rango de fechas con paso.

    :param start: fecha de inicio del rango.
    :param end: fecha de cierre del rango (inclusive).
    :param step: el intervalo del rango (positivo).
    :return: el rango de ``datetime`` de inicio a cierre.
    """

    post_process = lambda dt: dt  # noqa: E731
    if isinstance(start, datetime) and isinstance(end, datetime):
        are_naive = start.tzinfo is None and end.tzinfo is None
        are_utc = start.tzinfo == utc and end.tzinfo == utc

        # Los casos con otra zona son más complejos por el horario de verano.
        are_others = start.tzinfo and end.tzinfo and not are_utc

        if are_others and _tz_key(start.tzinfo) != _tz_key(end.tzinfo):
            raise ValueError("Timezones of start argument and end argument seem inconsistent")

        if not are_naive and not are_utc and not are_others:
            raise ValueError("Timezones of start argument and end argument mismatch")

        if not are_naive:
            range_tz = start.tzinfo
            post_process = lambda dt: dt.replace(tzinfo=range_tz)  # noqa: E731
            start = start.replace(tzinfo=None)
            end = end.replace(tzinfo=None)

    elif isinstance(start, date) and isinstance(end, date):
        if not isinstance(start + step, date):
            raise ValueError("the step interval must add only entire days")  # noqa: TRY004
    else:
        raise ValueError("start/end should be both date or both datetime type")  # noqa: TRY004

    if start > end:
        raise ValueError("start > end, start date must be before end")

    if start >= start + step:
        raise ValueError("Looks like step is null or negative")

    while start <= end:
        yield post_process(start)
        start += step


def sum_intervals(intervals: Iterable[tuple[datetime, datetime, ...]]) -> float:
    """Suma la duración de los intervalos, en horas."""
    return sum(
        (interval[1] - interval[0]).total_seconds() / 3600
        for interval in intervals
    )


def weeknumber(locale: babel.Locale, date: date, first_week_day: int | None = None) -> tuple[int, int]:
    """El año y el número de semana de ``date``. La semana es 1-indexada.

    Para los idiomas ISO (primer día = lunes, mínimo de días = 4) el concepto
    es claro y la biblioteca estándar de Python lo implementa directamente.

    Para el resto no hay una definición real. Aquí se implementa el criterio
    de primer-día-de-año sin partir: la primera semana del año es la que
    contiene el primer día del año (tomando en cuenta el primer día de
    semana), y los días del año anterior que caen en esa semana se consideran
    del año siguiente a efectos de calendario.

    Es decir, el 27 de diciembre de 2015 cae en la primera semana de 2016.

    La alternativa sería partir la semana en dos, de modo que la semana del 27
    de diciembre de 2015 al 2 de enero de 2016 fuera **a la vez** W53/2015 y
    W01/2016.

    :param first_week_day: sustituye al primer día de semana del idioma
        (0 = lunes, …, 6 = domingo). Con ``None`` se deriva del idioma.
    """
    if not first_week_day:
        first_week_day = locale.first_week_day
    if first_week_day == 0 and locale.min_week_days == 4:
        # nada que hacer
        return date.isocalendar()[:2]

    delta = relativedelta(weekday=weekdays[first_week_day](-1))
    # primero se busca el primer día de la primera semana del año siguiente;
    # si la fecha de referencia es posterior, cae en esa primera semana. Esto
    # se retira si algún día se implementan las semanas partidas.
    fdny = date.replace(year=date.year + 1, month=1, day=1) - delta
    if date >= fdny:
        return date.year + 1, 1

    # si no, el número de periodos de 7 días entre el primer día de la primera
    # semana y la referencia
    fdow = date.replace(month=1, day=1) - delta
    doy = (date - fdow).days

    return date.year, (doy // 7 + 1)


def weekstart(locale: babel.Locale, date: date):
    """El primer día de la semana que contiene a ``date``.

    Si ``date`` ya es ese día, se devuelve sin cambio. Si no, se retrocede al
    día más reciente que lo sea.

    Ejemplos con la semana empezando en domingo:

    - ``weekstart`` del sáb 30 ago → dom 24 ago
    - ``weekstart`` del sáb 23 ago → dom 17 ago
    """
    return date + relativedelta(weekday=weekdays[locale.first_week_day](-1))


def weekend(locale: babel.Locale, date: date):
    """El último día de la semana que contiene a ``date``.

    Si ``date`` ya es ese día, se devuelve sin cambio. Si no, se avanza al
    siguiente día que lo sea.

    Ejemplos con la semana empezando en domingo (y cerrando en sábado):

    - ``weekend`` del dom 24 ago → sáb 30 ago
    - ``weekend`` del sáb 30 ago → sáb 30 ago
    """
    return weekstart(locale, date) + relativedelta(days=6)
