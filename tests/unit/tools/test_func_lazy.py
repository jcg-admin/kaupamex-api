"""``tools.func.lazy`` — el proxy al resultado memoizado de una evaluación diferida.

Fiel a ``odoo19c: odoo/tools/func.py:135-262`` (LGPL-3).

Cada caso fija una conducta **por la que el símbolo se portó** en vez de
resolverse con ``functools.cached_property`` o con un ``lambda``: ninguno de
los dos es un *proxy* —el valor no se puede usar como si fuera el objeto
envuelto— y es justo eso lo que ``json_default`` y sus consumidores explotan.
"""
import pytest

from tools.func import lazy

pytestmark = pytest.mark.unit


# -- Evaluación diferida (``func.py:136-143``) -------------------------------

def test_does_not_call_the_function_when_built():
    """«func(arg) is not called yet» — el docstring de la fuente, verbatim."""
    calls = []
    lazy(lambda: calls.append(1))
    assert calls == []


def test_calls_the_function_on_the_first_access():
    """El primer uso del valor dispara la llamada, no antes."""
    calls = []

    def build():
        calls.append(1)
        return 42

    proxy = lazy(build)
    assert calls == []
    assert proxy + 0 == 42
    assert calls == [1]


def test_calls_the_function_only_once():
    """Memoizado: «the (memoized) result». Dos usos, una sola llamada."""
    calls = []

    def build():
        calls.append(1)
        return 7

    proxy = lazy(build)
    assert proxy + 1 == 8
    assert proxy + 2 == 9
    assert calls == [1]


def test_forwards_the_positional_and_keyword_arguments():
    """``lazy(func, *args, **kwargs)`` — la firma de ``__init__`` (``:145``)."""
    proxy = lazy(lambda a, b, c=0: (a, b, c), 1, 2, c=3)
    assert proxy._value == (1, 2, 3)


def test_releases_the_function_and_its_arguments_after_evaluating():
    """Tras evaluar, los tres campos quedan en ``None`` (``:152-157``).

    No es cosmético: mantener la referencia al llamable y a sus argumentos
    alarga su vida tanto como la del proxy, que es lo que la fuente evita.
    """
    proxy = lazy(lambda x: x * 2, 21)
    assert proxy._value == 42
    assert proxy._func is None
    assert proxy._args is None
    assert proxy._kwargs is None


# -- Proxy de atributos (``func.py:161-163``) --------------------------------

class _Holder:
    """Objeto con estado propio: el destino del proxy de atributos."""

    def __init__(self):
        self.name = 'first'

    def shout(self):
        return self.name.upper()


def test_reads_an_attribute_through_the_proxy():
    """``__getattr__`` delega en el valor (``:161``)."""
    proxy = lazy(_Holder)
    assert proxy.name == 'first'
    assert proxy.shout() == 'FIRST'


def test_writes_an_attribute_through_the_proxy():
    """``__setattr__`` escribe en el valor, no en el proxy (``:162``)."""
    proxy = lazy(_Holder)
    proxy.name = 'second'
    assert proxy._value.name == 'second'


def test_deletes_an_attribute_through_the_proxy():
    """``__delattr__`` borra del valor (``:163``)."""
    proxy = lazy(_Holder)
    del proxy.name
    assert not hasattr(proxy._value, 'name')


def test_has_no_instance_dictionary():
    """``__slots__`` declara los cuatro campos y nada más (``:143``)."""
    proxy = lazy(lambda: 1)
    assert not hasattr(proxy, '__dict__')


# -- Los protocolos que la fuente delega -------------------------------------

def test_string_conversions_use_the_value():
    """``__str__``, ``__bytes__`` y ``__format__`` (``:168-170``)."""
    proxy = lazy(lambda: 'text')
    assert str(proxy) == 'text'
    assert bytes(lazy(lambda: b'raw')) == b'raw'
    assert format(lazy(lambda: 3.5), '.2f') == '3.50'


def test_repr_hides_the_value_until_it_is_evaluated():
    """``__repr__`` — ``object.__repr__`` mientras no se haya evaluado (``:165``).

    Es la conducta que impide que un ``repr`` de depuración dispare el cálculo
    diferido, que sería exactamente lo contrario de lo que el proxy existe para
    hacer.
    """
    proxy = lazy(lambda: 'value')
    assert 'value' not in repr(proxy)
    assert proxy._value == 'value'
    assert repr(proxy) == repr('value')


def test_comparisons_use_the_value():
    """Los seis operadores de orden e igualdad (``:172-177``)."""
    proxy = lazy(lambda: 10)
    assert proxy == 10
    assert proxy != 11
    assert proxy < 11
    assert proxy <= 10
    assert proxy > 9
    assert proxy >= 10


def test_hash_and_truthiness_use_the_value():
    """``__hash__`` y ``__bool__`` (``:179-180``)."""
    assert hash(lazy(lambda: 'key')) == hash('key')
    assert bool(lazy(lambda: 1)) is True
    assert bool(lazy(lambda: 0)) is False


def test_the_container_protocol_uses_the_value():
    """``__len__``, ``__getitem__``, ``__iter__``, ``__contains__`` (``:184-192``)."""
    proxy = lazy(lambda: [1, 2, 3])
    assert len(proxy) == 3
    assert proxy[0] == 1
    assert list(proxy) == [1, 2, 3]
    assert list(reversed(proxy)) == [3, 2, 1]
    assert 2 in proxy


def test_the_arithmetic_protocol_uses_the_value():
    """El ejemplo literal del docstring de la fuente (``:139-141``)."""
    foo = lazy(lambda x: x, 10)
    assert foo + 1 == 11
    assert foo + 2 == 12
    assert foo - 1 == 9
    assert foo * 2 == 20


def test_the_reflected_arithmetic_uses_the_value():
    """Los operadores reflejados (``:210-224``) — el proxy a la derecha."""
    proxy = lazy(lambda: 10)
    assert 1 + proxy == 11
    assert 30 - proxy == 20


def test_calling_the_proxy_calls_the_value():
    """``__call__`` (``:182``) — envolver un llamable sigue siendo llamable."""
    proxy = lazy(lambda: (lambda x: x * 3))
    assert proxy(4) == 12


def test_the_numeric_conversions_use_the_value():
    """``__int__``, ``__float__``, ``__index__``, ``__abs__`` (``:241-251``)."""
    proxy = lazy(lambda: -3)
    assert int(proxy) == -3
    assert float(proxy) == -3.0
    assert abs(proxy) == 3
    assert [0, 1, 2, 3][lazy(lambda: 2)] == 2


def test_the_context_manager_protocol_uses_the_value():
    """``__enter__`` / ``__exit__`` (``:255-257``)."""
    class _Ctx:
        def __init__(self):
            self.entered = False

        def __enter__(self):
            self.entered = True
            return 'inside'

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    holder = _Ctx()
    proxy = lazy(lambda: holder)
    with proxy as value:
        assert value == 'inside'
    assert holder.entered is True
