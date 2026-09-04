"""``tools.json.json_default`` — las siete ramas del ``default=`` de ``json.dumps``.

Fiel a ``odoo19c: odoo/tools/json.py:62-76`` (LGPL-3).

``json.dumps`` llama a ``default`` **sólo** cuando no sabe serializar un
objeto, así que cada rama es un tipo que el codificador no conoce y una regla
de cómo representarlo. Hay un caso por rama, y luego un caso por el **orden**
entre las dos primeras: ``datetime`` es subclase de ``date``, así que
invertirlas convertiría todo instante en una fecha pelada sin que nada fallara.
"""
import datetime as dt
import json

import pytest

from orm.domains import Domain
from tools.func import lazy
from tools.json import json_default
from tools.misc import ReadonlyDict

pytestmark = pytest.mark.unit


# -- Rama 1: ``datetime`` (``json.py:64-65``) --------------------------------

def test_serializes_a_datetime_with_the_server_format():
    assert (json_default(dt.datetime(2026, 9, 2, 4, 5, 6))
            == '2026-09-02 04:05:06')


def test_the_datetime_branch_comes_before_the_date_branch():
    """``datetime`` es subclase de ``date``: el orden ES el contrato.

    Sin esta comprobación, invertir las dos primeras ramas dejaría la suite en
    verde y truncaría la hora de todo instante serializado.
    """
    assert issubclass(dt.datetime, dt.date)
    assert json_default(dt.datetime(2026, 9, 2, 4, 5, 6)).endswith('04:05:06')


# -- Rama 2: ``date`` (``json.py:66-67``) ------------------------------------

def test_serializes_a_date_with_the_server_format():
    assert json_default(dt.date(2026, 9, 2)) == '2026-09-02'


def test_the_date_branch_is_not_the_string_fallback():
    """La rama tiene que ser distinguible de ``str(obj)``, y casi no lo es.

    Para un año de cuatro cifras ``str(date)`` —que es su ISO 8601— y
    ``strftime('%Y-%m-%d')`` dan la **misma** cadena, así que anular la rama
    de ``date`` dejaría el caso de arriba en verde: mediría el ``str`` final y
    no la rama. Los dos se separan cuando el año no llena cuatro cifras, que
    es lo que este caso ejerce.
    """
    ancient = dt.date(1, 1, 1)
    assert str(ancient) == '0001-01-01'
    assert json_default(ancient) == '1-01-01'


# -- Rama 3: ``lazy`` (``json.py:68-69``) ------------------------------------

def test_serializes_a_lazy_proxy_as_its_evaluated_value():
    """Devuelve ``obj._value``, no ``str(obj)``: el valor sigue siendo un dato.

    La diferencia importa porque el resultado vuelve al codificador: un
    ``lazy`` que envuelve un ``dict`` se serializa como objeto JSON, no como la
    representación textual de un diccionario de Python.
    """
    assert json_default(lazy(lambda: {'a': 1})) == {'a': 1}


def test_the_lazy_branch_does_not_force_a_double_evaluation():
    """Serializar no vuelve a llamar al constructor diferido."""
    calls = []

    def build():
        calls.append(1)
        return 5

    proxy = lazy(build)
    assert json_default(proxy) == 5
    assert json_default(proxy) == 5
    assert calls == [1]


# -- Rama 4: ``ReadonlyDict`` (``json.py:70-71``) ----------------------------

def test_serializes_a_readonly_dict_as_a_plain_dict():
    result = json_default(ReadonlyDict({'foo': 'bar'}))
    assert result == {'foo': 'bar'}
    assert type(result) is dict


# -- Rama 5: ``bytes`` (``json.py:72-73``) -----------------------------------

def test_serializes_bytes_by_decoding_them():
    """``obj.decode()`` — UTF-8, y sin el prefijo ``b`` que daría ``str``."""
    assert json_default(b'text') == 'text'
    assert json_default('acento'.encode()) == 'acento'


# -- Rama 6: ``Domain`` (``json.py:74-75``) ----------------------------------

def test_serializes_a_domain_as_its_polish_notation_list():
    """``list(obj)`` — la forma de entrada y salida que la fuente conserva."""
    assert json_default(Domain('name', '=', 'x')) == [('name', '=', 'x')]


def test_serializes_a_compound_domain_keeping_its_operators():
    assert (json_default(Domain('a', '=', 1) & Domain('b', '=', 2))
            == ['&', ('a', '=', 1), ('b', '=', 2)])


# -- Rama 7: el resto (``json.py:76``) ---------------------------------------

def test_falls_back_to_the_string_representation():
    """Sin rama propia, ``str(obj)``: nunca lanza, siempre serializa algo."""
    class _Unknown:
        def __str__(self):
            return 'unknown-value'

    assert json_default(_Unknown()) == 'unknown-value'


def test_the_fallback_covers_a_type_json_would_reject():
    """Un ``set`` no tiene rama propia y ``json.dumps`` no lo conoce."""
    assert json_default({1}) == str({1})


# -- Integración: es el ``default=`` de ``json.dumps`` -----------------------

def test_works_as_the_default_hook_of_json_dumps():
    """El uso real: el codificador llama a la función por cada objeto opaco."""
    payload = {
        'when': dt.datetime(2026, 9, 2, 4, 5, 6),
        'day': dt.date(2026, 9, 2),
        'raw': b'text',
        'frozen': ReadonlyDict({'foo': 'bar'}),
        'deferred': lazy(lambda: 7),
    }
    assert json.loads(json.dumps(payload, default=json_default)) == {
        'when': '2026-09-02 04:05:06',
        'day': '2026-09-02',
        'raw': 'text',
        'frozen': {'foo': 'bar'},
        'deferred': 7,
    }
