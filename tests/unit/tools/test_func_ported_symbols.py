"""``tools.func`` — los siete simbolos que el archivo declaraba ausentes.

El docstring del archivo declaraba **tres portados y siete ausentes**, con un
criterio explicito: *«un simbolo llega aqui cuando un modulo portado lo
importa»*. Ese criterio esta retirado — no se espera al consumidor, porque el
consumidor tambien se implementa. Al tocar un archivo con simbolos pendientes
se implementan todos, tenga o no quien los llame hoy.

Los casos se escribieron ANTES del porte: contra el archivo viejo la
importacion entera falla.
"""
import functools
import inspect
import os
import threading
import warnings

import pytest

from tools.func import (
    classproperty,
    conditional,
    filter_kwargs,
    frame_codeinfo,
    lazy_classproperty,
    lazy_property,
    locked,
    synchronized,
)


class TestConditional:
    """Aplica el decorador solo si la condicion es verdadera."""

    def test_the_true_condition_applies_the_decorator(self):
        def shout(fn):
            return lambda: fn().upper()

        @conditional(True, shout)
        def hello():
            return 'hola'

        assert hello() == 'HOLA'

    def test_the_false_condition_leaves_the_function_alone(self):
        def shout(fn):
            return lambda: fn().upper()

        @conditional(False, shout)
        def hello():
            return 'hola'

        assert hello() == 'hola'

    @pytest.mark.parametrize('falsy', [0, '', None, [], {}])
    def test_it_reads_truthiness_not_identity(self, falsy):
        """``if condition``, no ``is True``: cualquier falsy no aplica."""
        @conditional(falsy, lambda fn: 'sustituido')
        def hello():
            return 'hola'

        assert hello() == 'hola'


class TestFilterKwargs:
    """Deja pasar solo los kwargs que la firma sabe recibir."""

    def test_it_drops_what_the_signature_does_not_name(self):
        def target(a, b=2):
            return a, b

        assert filter_kwargs(target, {'a': 1, 'b': 2, 'c': 3}) == {'a': 1, 'b': 2}

    def test_the_keyword_only_parameter_counts(self):
        def target(a, *, b):
            return a, b

        assert filter_kwargs(target, {'a': 1, 'b': 2, 'z': 9}) == {'a': 1, 'b': 2}

    def test_the_var_keyword_lets_everything_through(self):
        """``**kwargs`` en la firma vacia el descarte: pasa todo."""
        def target(a, **rest):
            return a, rest

        given = {'a': 1, 'nunca_declarado': 2}
        assert filter_kwargs(target, given) == given

    def test_it_returns_the_same_object_when_nothing_is_dropped(self):
        """La fuente devuelve ``kwargs`` tal cual si no sobra ninguno."""
        def target(a, b):
            return a, b

        given = {'a': 1, 'b': 2}
        assert filter_kwargs(target, given) is given

    def test_the_positional_only_parameter_is_dropped(self):
        """El control: si la firma no admite el nombre como clave, se cae."""
        def target(a, /, b):
            return a, b

        assert filter_kwargs(target, {'a': 1, 'b': 2}) == {'b': 2}


class TestSynchronized:
    """El decorador que toma el cerrojo del propio objeto antes de entrar."""

    def test_it_takes_the_lock_named_by_the_attribute(self):
        seen = []

        class Sensor:
            def __init__(self):
                self._lock = _RecordingLock(seen)

            @synchronized()
            def work(self, value):
                seen.append(('body', value))
                return value * 2

        assert Sensor().work(3) == 6
        assert seen == [('acquire',), ('body', 3), ('release',)]

    def test_the_attribute_name_is_a_parameter(self):
        seen = []

        class Sensor:
            def __init__(self):
                self._other = _RecordingLock(seen)

            @synchronized('_other')
            def work(self):
                return 'listo'

        assert Sensor().work() == 'listo'
        assert seen == [('acquire',), ('release',)]

    def test_it_keeps_the_wrapped_identity(self):
        class Sensor:
            _lock = threading.RLock()

            @synchronized()
            def work(self):
                """Su docstring."""

        assert Sensor.work.__name__ == 'work'
        assert Sensor.work.__doc__ == 'Su docstring.'

    def test_it_releases_when_the_body_raises(self):
        """El ``with`` es lo que lo garantiza; sin el, el cerrojo se queda."""
        seen = []

        class Sensor:
            def __init__(self):
                self._lock = _RecordingLock(seen)

            @synchronized()
            def work(self):
                raise ValueError('revienta')

        with pytest.raises(ValueError):
            Sensor().work()
        assert seen == [('acquire',), ('release',)]


class _RecordingLock:
    """Un cerrojo que anota lo que le hacen — el instrumento de la prueba."""

    def __init__(self, log):
        self._log = log

    def __enter__(self):
        self._log.append(('acquire',))
        return self

    def __exit__(self, *exc):
        self._log.append(('release',))
        return False


class TestLocked:
    """``locked`` es ``synchronized()`` ya aplicado, sobre ``_lock``."""

    def test_it_is_the_default_application(self):
        seen = []

        class Sensor:
            def __init__(self):
                self._lock = _RecordingLock(seen)

            @locked
            def work(self):
                return 'listo'

        assert Sensor().work() == 'listo'
        assert seen == [('acquire',), ('release',)]


class TestFrameCodeinfo:
    """Devuelve ``(archivo, linea)`` de un marco anterior — nunca levanta.

    El nombre esperado sale de ``__file__``, no de un literal: un literal se
    queda atras al renombrar el archivo y el caso falla sin que nada haya
    cambiado en lo medido. Ocurrio al renombrar este mismo archivo.
    """

    def test_it_reads_the_current_frame(self):
        filename, lineno = frame_codeinfo(inspect.currentframe())
        assert filename.endswith(os.path.basename(__file__))
        assert isinstance(lineno, int)

    def test_it_walks_back_the_requested_number_of_frames(self):
        def inner():
            return frame_codeinfo(inspect.currentframe(), 1)

        filename, _lineno = inner()
        assert filename.endswith(os.path.basename(__file__))

    def test_the_absent_frame_is_unknown_not_an_error(self):
        assert frame_codeinfo(None) == ("<unknown>", '')

    def test_it_swallows_what_it_cannot_read(self):
        """El control: un objeto que no es frame no revienta al que llama."""
        assert frame_codeinfo(object()) == ("<unknown>", '')


class TestLazyProperty:
    """Obsoleto desde 19: se porta CON su aviso, como en la fuente."""

    def test_it_warns_when_declared(self):
        with pytest.warns(DeprecationWarning, match='lazy_property'):
            class Sensor:
                @lazy_property
                def value(self):
                    return 42

    def test_it_still_caches_like_cached_property(self):
        calls = []

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)

            class Sensor:
                @lazy_property
                def value(self):
                    calls.append(1)
                    return 42

        sensor = Sensor()
        assert sensor.value == 42
        assert sensor.value == 42
        assert len(calls) == 1

    def test_it_is_a_cached_property(self):
        assert issubclass(lazy_property, functools.cached_property)

    def test_reset_all_warns_and_resets(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)

            class Sensor:
                @lazy_property
                def value(self):
                    return object()

        sensor = Sensor()
        first = sensor.value
        with pytest.warns(DeprecationWarning, match='reset_cache_properties'):
            lazy_property.reset_all(sensor)
        assert sensor.value is not first


class TestLazyClassproperty:
    """Como ``classproperty``, pero se cachea EN LA CLASE tras el primer uso."""

    def test_it_computes_from_the_class(self):
        class Sensor:
            @lazy_classproperty
            def value(cls):
                return cls.__name__.upper()

        assert Sensor.value == 'SENSOR'

    def test_it_replaces_itself_on_the_owner(self):
        calls = []

        class Sensor:
            @lazy_classproperty
            def value(cls):
                calls.append(1)
                return 7

        assert Sensor.value == 7
        assert Sensor.value == 7
        assert len(calls) == 1
        assert Sensor.__dict__['value'] == 7

    def test_the_plain_classproperty_does_not_cache(self):
        """El control que los separa: sin este caso los dos casos de arriba
        pasarian con un ``classproperty`` a secas."""
        calls = []

        class Sensor:
            @classproperty
            def value(cls):
                calls.append(1)
                return 7

        assert Sensor.value == 7
        assert Sensor.value == 7
        assert len(calls) == 2
        assert isinstance(Sensor.__dict__['value'], classproperty)
