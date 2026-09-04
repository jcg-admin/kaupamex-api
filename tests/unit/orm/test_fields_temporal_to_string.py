"""``Date.to_string`` y ``Datetime.to_string`` — el formato del servidor.

Fiel a ``odoo19c: odoo/orm/fields_temporal.py:164-173`` y ``:255-264``
(LGPL-3).

Los dos ya vivían en ``orm/fields_temporal.py`` cuando la tarea #142 los pidió
—medido: ``Date.to_string`` y ``Datetime.to_string`` resuelven sobre el
despachador y sobre la clase de Django—, así que este módulo no los porta:
**fija su contrato**, que es la precondición de las dos primeras ramas de
``tools.json.json_default``.

La conducta que se mide no es «convierte una fecha»: es que devuelve
``False`` —no ``None``, no cadena vacía— ante un valor falso, y que el formato
no lleva zona ni microsegundos. Un consumidor que serialice el resultado
depende de las tres cosas.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from orm.fields_temporal import Date, Datetime
from tools.misc import (DEFAULT_SERVER_DATE_FORMAT,
                        DEFAULT_SERVER_DATETIME_FORMAT)

pytestmark = pytest.mark.unit


# -- ``Date.to_string`` (``fields_temporal.py:164-173``) ---------------------

def test_date_to_string_uses_the_server_date_format():
    """El formato es el declarado, no uno escrito a mano en el porte."""
    assert Date.to_string(dt.date(2026, 9, 2)) == '2026-09-02'
    assert DEFAULT_SERVER_DATE_FORMAT == '%Y-%m-%d'


def test_date_to_string_truncates_the_time_part():
    """«the hours, minute, seconds, tzinfo will be truncated» — verbatim."""
    assert Date.to_string(dt.datetime(2026, 9, 2, 4, 5, 6)) == '2026-09-02'


def test_date_to_string_truncates_the_timezone():
    """Un instante con zona pierde la zona, no se convierte a otra."""
    aware = dt.datetime(2026, 9, 2, 4, 5, 6,
                        tzinfo=ZoneInfo('America/Mexico_City'))
    assert Date.to_string(aware) == '2026-09-02'


def test_date_to_string_returns_false_for_a_falsy_value():
    """``if value else False`` — devuelve ``False``, no ``None`` ni ``''``.

    Es lo que distingue esta conducta de un ``strftime`` pelado, y lo que
    permite a un llamador escribir ``value = Date.to_string(x) or default``.
    """
    assert Date.to_string(False) is False
    assert Date.to_string(None) is False


# -- ``Datetime.to_string`` (``fields_temporal.py:255-264``) -----------------

def test_datetime_to_string_uses_the_server_datetime_format():
    """Fecha y hora separadas por un espacio, sin la ``T`` de ISO 8601."""
    assert (Datetime.to_string(dt.datetime(2026, 9, 2, 4, 5, 6))
            == '2026-09-02 04:05:06')
    assert DEFAULT_SERVER_DATETIME_FORMAT == '%Y-%m-%d %H:%M:%S'


def test_datetime_to_string_drops_the_microseconds():
    """El formato no los declara: se pierden en silencio, como en la fuente."""
    value = dt.datetime(2026, 9, 2, 4, 5, 6, 123456)
    assert Datetime.to_string(value) == '2026-09-02 04:05:06'


def test_datetime_to_string_puts_a_bare_date_at_midnight():
    """«if `value` is of type `date`, the time portion will be midnight»."""
    assert Datetime.to_string(dt.date(2026, 9, 2)) == '2026-09-02 00:00:00'


def test_datetime_to_string_keeps_the_wall_clock_of_an_aware_value():
    """La zona no se convierte ni se anota: el formato no lleva ``%z``.

    La conversión a la zona del cliente es trabajo de ``context_timestamp``,
    que ``convert_to_display_name`` aplica **antes** de llamar aquí
    (``fields_temporal.py:290-293``). ``to_string`` sola no la hace.
    """
    aware = dt.datetime(2026, 9, 2, 4, 5, 6,
                        tzinfo=ZoneInfo('America/Mexico_City'))
    assert Datetime.to_string(aware) == '2026-09-02 04:05:06'


def test_datetime_to_string_returns_false_for_a_falsy_value():
    """Mismo contrato que su hermano: ``False``, no ``None``."""
    assert Datetime.to_string(False) is False
    assert Datetime.to_string(None) is False
