"""Campos temporales — fiel a ``odoo/orm/fields_temporal.py`` (Odoo 19).

``Date`` y ``Datetime``, los dos como **despachadores** de
``company_dependent`` (tarea #129) y no como alias pelados: los dos tipos
están en ``COMPANY_DEPENDENT_FIELDS``
(``odoo19c: odoo/orm/fields.py:42-44``).

Sus consumidores en la fuente están en el addon de prueba
(``odoo/addons/test_orm/models/test_orm.py:725-726``), no en código de
producto. Se cablean igual porque la lista de tipos admitidos es de la fuente:
que hoy sólo la ejerciten sus propias pruebas no la acorta — el mismo criterio
con que ``COMPANY_DEPENDENT_FIELDS`` se copió entera y no filtrada.

FORMA DEL PORTE — dos mecanismos, ninguno inventado aquí
========================================================

La fuente declara ``BaseDate`` como clase base de campo y cuelga de ella
``Date`` y ``Datetime``, cada uno con sus constructores y convertidores como
``staticmethod``. Aquí el almacenamiento ya lo pone Django, así que la misma
superficie aterriza con los dos mecanismos que este árbol ya usa:

1. **Los métodos del protocolo de campo** —``expression_getter``,
   ``_expression_property_getter``, ``property_to_sql``,
   ``convert_to_column``, ``convert_to_cache``, ``convert_to_export``,
   ``convert_to_display_name``— se **adjuntan** a ``models.DateField`` y
   ``models.DateTimeField`` al importar este módulo. Es exactamente lo que
   ``orm/fields.py`` hace con ``models.Field`` (``to_sql``,
   ``property_to_sql``, ``expression_getter``) y por su misma razón, citada
   allá: *«un campo de Django no es nuestro para subclasificar, pero el nombre
   y la firma se conservan»*. Adjuntar a la subclase **sobreescribe** lo de
   ``models.Field`` por resolución de atributo, que es la relación
   ``BaseDate`` → ``Field`` de la fuente.

   Y hay una razón de datos para no subclasificar: el autodetector de
   migraciones de Django compara la **ruta** de la clase del campo, así que
   una subclase nuestra emitiría un ``AlterField`` por cada campo de fecha del
   árbol — churn de migración sin cambio de columna.

2. **Los constructores estáticos** —``Date.today``, ``Datetime.now``,
   ``to_date``, ``from_string``…— se cuelgan del **despachador**, que es una
   función y no admite decoradores de clase. La forma de llamada queda
   literal: ``fields.Date.today()``. Se cuelgan también en las dos clases de
   Django, para que un campo ya instanciado responda igual que allá.

**``models.DateTimeField`` es subclase de ``models.DateField``** —medido—, así
que todo lo que ``Datetime`` redefine se adjunta explícitamente a las dos:
dejar una sola heredaría el valor de fecha, que es el defecto contrario.

DIVERGENCIA DE MECANISMO, declarada: la fuente resuelve zonas horarias con
``pytz``, que **no está instalado** aquí —medido—; el equivalente de la
biblioteca estándar es ``zoneinfo``, que lee la misma base de datos IANA. Es
la misma adaptación que ``res_users._set_tz_from_request`` y
``orm.environments.get_current_tz`` ya declaran.
"""
import logging
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, available_timezones

from django.db import models

from orm.environments import get_context, get_current_tz
from orm.fields_company_dependent import make_dispatcher
from orm.utils import READ_GROUP_NUMBER_GRANULARITY, parse_field_expr
from tools import date_utils
from tools.misc import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
from tools.misc import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT
from tools.sql import SQL

_logger = logging.getLogger(__name__)

__all__ = ['Date', 'Datetime', 'DATE_LENGTH', 'DATETIME_LENGTH']

#: ≙ ``odoo19c: odoo/orm/fields_temporal.py:23-24``. Se **calculan** del propio
#: formato, como la fuente, para que los dos no puedan divergir.
#: ``DATE_LENGTH`` está duplicado en ``tools/misc.py`` — también lo está en la
#: fuente (``odoo/tools/misc.py:541``), así que la duplicación se porta.
DATE_LENGTH = len(date.today().strftime(DATE_FORMAT))
DATETIME_LENGTH = len(datetime.now().strftime(DATETIME_FORMAT))


# === BaseDate — las propiedades comunes de Date y Datetime ==================
# ≙ ``BaseDate`` (``odoo19c: fields_temporal.py:27-101``).

def _base_date_expression_getter(self, field_expr):
    """``expression_getter`` — ≙ ``BaseDate.expression_getter`` (``:35-41``).

    La fuente devuelve ``self.__get__`` porque sus campos son descriptores;
    aquí es ``getattr(record, self.name)``, la misma divergencia que
    ``orm/fields.py`` ya declara para el caso base.
    """
    _fname, property_name = parse_field_expr(field_expr)
    if not property_name:
        if field_expr == self.name:
            return lambda record: getattr(record, self.name)
        raise ValueError(f'Expression not supported on {self}: {field_expr!r}')

    get_property = self._expression_property_getter(property_name)
    return lambda record: (
        (value := getattr(record, self.name)) and get_property(value))


def _base_date_expression_property_getter(self, property_name):
    """``_expression_property_getter`` — ≙ ``:43-77``.

    Devuelve la función que mapea un valor (fecha o fecha-hora) al
    ``property_name`` pedido.
    """
    match property_name:
        case 'tz':
            return lambda value: value
        case 'year_number':
            return lambda value: value.year
        case 'quarter_number':
            return lambda value: value.month // 4 + 1
        case 'month_number':
            return lambda value: value.month
        case 'iso_week_number':
            return lambda value: value.isocalendar().week
        case 'day_of_year':
            return lambda value: value.timetuple().tm_yday
        case 'day_of_month':
            return lambda value: value.day
        case 'day_of_week':
            return lambda value: value.timetuple().tm_wday
        case 'hour_number' if self.type == 'datetime':
            return lambda value: value.hour
        case 'minute_number' if self.type == 'datetime':
            return lambda value: value.minute
        case 'second_number' if self.type == 'datetime':
            return lambda value: value.second
        case 'hour_number' | 'minute_number' | 'second_number':
            # para las fechas siempre es 0
            return lambda value: 0
    assert property_name not in READ_GROUP_NUMBER_GRANULARITY, \
        f"Property not implemented {property_name}"
    raise ValueError(
        f"Error when processing the granularity {property_name} is not "
        f"supported. Only "
        f"{', '.join(READ_GROUP_NUMBER_GRANULARITY.keys())} are supported")


def _base_date_property_to_sql(self, field_sql, property_name, model=None,
                               alias=None, query=None):
    """``property_to_sql`` — ≙ ``:80-95``. La expresión SQL de la granularidad.

    La fuente lee la zona de ``model.env.context``; aquí el contexto es de
    proceso (``orm.environments.get_context``). ``model``, ``alias`` y ``query``
    se conservan en la firma —el llamador de la fuente los pasa
    posicionalmente— y quedan sin uso.
    """
    sql_expr = field_sql
    if self.type == 'datetime' and (tz_name := get_context().get('tz')):
        # sólo se usa la zona que viene del contexto
        if tz_name in available_timezones():
            sql_expr = SQL("timezone(%s, timezone('UTC', %s))",
                           tz_name, sql_expr)
        else:
            _logger.warning("Grouping in unknown / legacy timezone %r", tz_name)
    if property_name == 'tz':
        # sólo se fija la zona
        return sql_expr
    if property_name not in READ_GROUP_NUMBER_GRANULARITY:
        raise ValueError(
            f'Error when processing the granularity {property_name} is not '
            f'supported. Only '
            f'{", ".join(READ_GROUP_NUMBER_GRANULARITY.keys())} are supported')
    granularity = READ_GROUP_NUMBER_GRANULARITY[property_name]
    return SQL('date_part(%s, %s)', granularity, sql_expr)


def _base_date_convert_to_column(self, value, record, values=None,
                                 validate=True):
    """``convert_to_column`` — ≙ ``:97-101``.

    psycopg escribe ``date``/``datetime`` directamente; la excepción es el
    campo dependiente de empresa, que espera cadena porque su columna es
    ``jsonb``.
    """
    value = self.convert_to_cache(value, record, validate=validate)
    if value and self.company_dependent:
        value = self.to_string(value)
    return value


# === Date — los constructores y convertidores ===============================
# ≙ ``Date`` (``odoo19c: fields_temporal.py:104-190``). La fuente los declara
# ``@staticmethod`` dentro de la clase; aquí viven en el módulo y se adjuntan
# tanto al despachador como a la clase de Django.

def _date_today(*args):
    """``Date.today`` — ≙ ``:113-118``. El día en curso, en formato del ORM.

    .. note:: Sirve para calcular valores por omisión.
    """
    return date.today()


def _date_context_today(record=None, timestamp=None):
    """``Date.context_today`` — ≙ ``:120-135``. Hoy en la zona del cliente.

    ``record`` se conserva en la firma —la fuente obtiene de él la zona— pero
    aquí la resuelve ``orm.environments.get_current_tz()``, porque el entorno
    es de proceso y no cuelga del recordset. Por eso admite ``None``.

    :param record: recordset del que la fuente obtiene la zona.
    :param timestamp: fecha-hora opcional en lugar de la actual (tiene que ser
        ``datetime``: una fecha pelada no se puede convertir entre zonas).
    """
    today = timestamp or datetime.now()
    tz = get_current_tz()
    today_utc = today.replace(tzinfo=timezone.utc)  # UTC = sin horario de verano
    return today_utc.astimezone(tz).date()


def _date_to_date(value):
    """``Date.to_date`` — ≙ ``:137-158``. Convierte ``value`` a :class:`date`.

    .. warning::

        Si recibe un ``datetime`` lo convierte a ``date`` y **pierde** toda la
        información propia de la hora (HMS, zona…).
    """
    if not value:
        return None
    if isinstance(value, date):
        if isinstance(value, datetime):
            return value.date()
        return value
    value = value[:DATE_LENGTH]
    return datetime.strptime(value, DATE_FORMAT).date()


def _date_to_string(value):
    """``Date.to_string`` — ≙ ``:164-173``. De ``date``/``datetime`` a cadena.

    Si ``value`` es un ``datetime``, la hora, los minutos, los segundos y la
    zona se truncan.
    """
    return value.strftime(DATE_FORMAT) if value else False


def _date_convert_to_cache(self, value, record, validate=True):
    """``Date.convert_to_cache`` — ≙ ``:175-182``."""
    if not value:
        return None
    if isinstance(value, datetime):
        # TODO: better fix data files (crm demo data)
        value = value.date()
    return _date_to_date(value)


def _date_convert_to_export(self, value, record):
    """``Date.convert_to_export`` — ≙ ``:184-185``."""
    return _date_to_date(value) or ''


def _date_convert_to_display_name(self, value, record):
    """``Date.convert_to_display_name`` — ≙ ``:187-188``."""
    return _date_to_string(value)


# === Datetime ===============================================================
# ≙ ``Datetime`` (``odoo19c: fields_temporal.py:191-300``).

def _datetime_now(*args):
    """``Datetime.now`` — ≙ ``:198-204``. Día y hora en formato del ORM.

    .. note:: Sirve para calcular valores por omisión.
    """
    # los microsegundos se aniquilan: no caben en el formato del servidor
    return datetime.now().replace(microsecond=0)


def _datetime_today(*args):
    """``Datetime.today`` — ≙ ``:206-209``. El día en curso, a medianoche."""
    return _datetime_now().replace(hour=0, minute=0, second=0)


def _datetime_context_timestamp(record, timestamp):
    """``Datetime.context_timestamp`` — ≙ ``:211-228``. A la zona del cliente.

    .. note:: **No** sirve como valor por omisión — los campos de fecha y hora
        se convierten solos al mostrarse en el cliente. Para eso está
        :func:`_datetime_now`.

    Como en :func:`_date_context_today`, ``record`` se conserva en la firma y
    la zona la resuelve ``get_current_tz()``.

    :param timestamp: fecha-hora ingenua (expresada en UTC) a convertir.
    :return: la misma marca, con zona, en la del contexto.
    """
    assert isinstance(timestamp, datetime), 'Datetime instance expected'
    tz = get_current_tz()
    utc_timestamp = timestamp.replace(tzinfo=timezone.utc)  # UTC = sin DST
    return utc_timestamp.astimezone(tz)


def _datetime_to_datetime(value):
    """``Datetime.to_datetime`` — ≙ ``:230-249``. Convierte a :class:`datetime`."""
    if not value:
        return None
    if isinstance(value, date):
        if isinstance(value, datetime):
            if value.tzinfo:
                raise ValueError(
                    "Datetime field expects a naive datetime: %s" % value)
            return value
        return datetime.combine(value, time.min)

    # TODO: fix data files
    return datetime.strptime(value, DATETIME_FORMAT[:len(value) - 2])


def _datetime_to_string(value):
    """``Datetime.to_string`` — ≙ ``:255-264``. De ``datetime``/``date`` a cadena.

    Si ``value`` es un ``date``, la parte horaria queda a medianoche.
    """
    return value.strftime(DATETIME_FORMAT) if value else False


def _datetime_expression_getter(self, field_expr):
    """``Datetime.expression_getter`` — ≙ ``:266-281``.

    Aplica la zona del contexto **antes** de extraer la granularidad, que es lo
    que distingue a éste del de ``BaseDate``.
    """
    if field_expr == self.name:
        return lambda record: getattr(record, self.name)
    _fname, property_name = parse_field_expr(field_expr)
    get_property = self._expression_property_getter(property_name)

    def getter(record):
        dt = getattr(record, self.name)
        if not dt:
            return False
        tz_name = get_context().get('tz')
        if tz_name and tz_name in available_timezones():
            # sólo se usa la zona que viene del contexto
            dt = dt.astimezone(ZoneInfo(tz_name))
        return get_property(dt)

    return getter


def _datetime_convert_to_cache(self, value, record, validate=True):
    """``Datetime.convert_to_cache`` — ≙ ``:283-284``."""
    return _datetime_to_datetime(value)


def _datetime_convert_to_export(self, value, record):
    """``Datetime.convert_to_export`` — ≙ ``:286-288``."""
    value = self.convert_to_display_name(value, record)
    return _datetime_to_datetime(value) or ''


def _datetime_convert_to_display_name(self, value, record):
    """``Datetime.convert_to_display_name`` — ≙ ``:290-293``."""
    if not value:
        return False
    return _datetime_to_string(_datetime_context_timestamp(record, value))


# === Adjuntar: el equivalente exacto de declarar el método en la clase ======

def _attach_base_date(field_class, type_name, column_type):
    """Cuelga de ``field_class`` lo que la fuente declara en ``BaseDate``.

    Medido antes de adjuntar: de los nombres que este módulo pone, sólo
    ``expression_getter`` y ``property_to_sql`` existían ya — y son
    **nuestros**, los que ``orm/fields.py`` cuelga de ``models.Field``.
    Adjuntarlos aquí los sobreescribe por resolución de atributo, que es la
    relación ``BaseDate`` → ``Field`` de la fuente.
    """
    #: ``type`` y ``_column_type`` — los declara cada clase concreta allá
    #: (``:107-108`` y ``:194-195``).
    field_class.type = type_name
    field_class._column_type = column_type
    #: ``convert_to_column`` lo consulta. En un campo escalar de Django es
    #: siempre falso: el mapa por empresa lo declara ``CompanyDependent``.
    field_class.company_dependent = False
    #: Los cuatro alias de fecha de ``BaseDate`` (``:30-33``).
    field_class.start_of = staticmethod(date_utils.start_of)
    field_class.end_of = staticmethod(date_utils.end_of)
    field_class.add = staticmethod(date_utils.add)
    field_class.subtract = staticmethod(date_utils.subtract)
    field_class.expression_getter = _base_date_expression_getter
    field_class._expression_property_getter = \
        _base_date_expression_property_getter
    field_class.property_to_sql = _base_date_property_to_sql
    field_class.convert_to_column = _base_date_convert_to_column


_attach_base_date(models.DateField, 'date', ('date', 'date'))
_attach_base_date(models.DateTimeField, 'datetime', ('timestamp', 'timestamp'))

models.DateField.today = staticmethod(_date_today)
models.DateField.context_today = staticmethod(_date_context_today)
models.DateField.to_date = staticmethod(_date_to_date)
#: Se conserva por compatibilidad, como la fuente: considerar ``from_string``
#: obsoleto (``:160-162``).
models.DateField.from_string = staticmethod(_date_to_date)
models.DateField.to_string = staticmethod(_date_to_string)
models.DateField.convert_to_cache = _date_convert_to_cache
models.DateField.convert_to_export = _date_convert_to_export
models.DateField.convert_to_display_name = _date_convert_to_display_name

models.DateTimeField.now = staticmethod(_datetime_now)
models.DateTimeField.today = staticmethod(_datetime_today)
models.DateTimeField.context_timestamp = staticmethod(
    _datetime_context_timestamp)
models.DateTimeField.to_datetime = staticmethod(_datetime_to_datetime)
#: Ídem ``Date.from_string`` — obsoleto, conservado (``:251-253``).
models.DateTimeField.from_string = staticmethod(_datetime_to_datetime)
models.DateTimeField.to_string = staticmethod(_datetime_to_string)
models.DateTimeField.expression_getter = _datetime_expression_getter
models.DateTimeField.convert_to_cache = _datetime_convert_to_cache
models.DateTimeField.convert_to_export = _datetime_convert_to_export
models.DateTimeField.convert_to_display_name = _datetime_convert_to_display_name


Date = make_dispatcher('Date', 'date', models.DateField)
Datetime = make_dispatcher('Datetime', 'datetime', models.DateTimeField)

# Los constructores estáticos, también en el despachador: es lo que hace que
# ``fields.Date.today()`` —la forma literal de la fuente— resuelva. Un
# despachador es una función: admite atributos, no decoradores de clase.
Date.start_of = date_utils.start_of
Date.end_of = date_utils.end_of
Date.add = date_utils.add
Date.subtract = date_utils.subtract
Date.today = _date_today
Date.context_today = _date_context_today
Date.to_date = _date_to_date
Date.from_string = _date_to_date
Date.to_string = _date_to_string

Datetime.start_of = date_utils.start_of
Datetime.end_of = date_utils.end_of
Datetime.add = date_utils.add
Datetime.subtract = date_utils.subtract
Datetime.now = _datetime_now
Datetime.today = _datetime_today
Datetime.context_timestamp = _datetime_context_timestamp
Datetime.to_datetime = _datetime_to_datetime
Datetime.from_string = _datetime_to_datetime
Datetime.to_string = _datetime_to_string
