"""``tools.func`` medido contra la fuente ejecutada.

``test_func_lazy.py`` fija a mano las conductas por las que ``lazy`` se portó;
este archivo **ejecuta** ``odoo19c: odoo/tools/func.py`` y compara, método por
método, qué hace cada uno con el valor envuelto. Se puede porque el módulo de
la referencia sólo importa la biblioteca estándar: se carga por ruta, sin
escribir nada en ``odoo-tools``.

``lazy`` delega cada método especial en el valor memoizado, y la forma de esa
delegación **es** el contrato: ``__lt__`` no llama a ``value.__lt__`` sino a
``other > value``, y ``__add__`` llama a ``value.__add__`` explícitamente en
vez de usar ``+``. Por eso el valor envuelto es un *registrador*: anota cada
método especial que recibe, con sus argumentos, y la prueba compara el
resultado **y** el registro de los dos módulos.

*Métrica:* para cada método que la fuente declara en ``lazy``, el valor
devuelto —o el nombre de la excepción— y la secuencia de métodos especiales
que llegó al valor envuelto; más la conducta de ``lazy_property``,
``classproperty`` y ``lazy_classproperty``.
*Ciega a:* un valor envuelto real que reaccione distinto al registrador —el
registrador devuelve fichas fijas—, y a toda divergencia que la fuente comparta
con nosotros, porque el oráculo es ella.
"""
import importlib.util
import pathlib
import warnings

import pytest

from tools import func as ported

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_func', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

#: Métodos de ``lazy`` que no delegan un método especial y se miden aparte.
NOT_DELEGATING = frozenset({'__init__', '__repr__', '__getattr__',
                            '__setattr__', '__delattr__'})

#: Argumentos con que se invoca cada método; el resto no recibe ninguno.
ARGUMENTS = {
    '__format__': ('>3',),
    '__call__': (1,),
    '__getitem__': ('k',),
    '__missing__': ('k',),
    '__delitem__': ('k',),
    '__contains__': ('k',),
    '__setitem__': ('k', 1),
    '__exit__': ('<type>', '<error>', '<traceback>'),
    '__aexit__': ('<type>', '<error>', '<traceback>'),
}
UNARY = frozenset({
    '__str__', '__bytes__', '__hash__', '__bool__', '__len__', '__iter__',
    '__reversed__', '__neg__', '__pos__', '__abs__', '__invert__',
    '__complex__', '__int__', '__float__', '__index__', '__round__',
    '__trunc__', '__floor__', '__ceil__', '__enter__', '__await__',
    '__aiter__', '__anext__', '__aenter__'})

#: Lo que el registrador devuelve cuando el protocolo exige un tipo concreto.
TYPED_RESULTS = {
    '__str__': '<str>', '__repr__': '<repr>', '__format__': '<format>',
    '__bytes__': b'<bytes>', '__hash__': 7, '__len__': 7, '__index__': 7,
    '__int__': 7, '__bool__': True, '__contains__': True, '__float__': 7.0,
    '__complex__': 7j,
}


def reference_module():
    """Carga ``odoo/tools/func.py`` de la referencia, o rinde None."""
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    path = root / 'odoo' / 'tools' / 'func.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('reference_func', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


def delegated_names(module):
    return sorted(
        name for name, value in vars(module.lazy).items()
        if name.startswith('__') and callable(value)
        and name not in NOT_DELEGATING)


def recorder_class(names):
    """Una clase que anota cada método especial que recibe, en orden."""

    def method(name):
        def record(self, *args):
            self.log.append((name, args))
            if name in ('__iter__', '__reversed__'):
                return iter(('<item>',))
            return TYPED_RESULTS.get(name, f'<{name}>')
        record.__name__ = name
        return record

    def getattr_(self, name):
        self.log.append(('__getattr__', (name,)))
        return f'<attr {name}>'

    def setattr_(self, name, value):
        self.log.append(('__setattr__', (name, value)))

    def delattr_(self, name):
        self.log.append(('__delattr__', (name,)))

    def init(self):
        object.__setattr__(self, 'log', [])

    namespace = {name: method(name) for name in names}
    namespace.update(__init__=init, __getattr__=getattr_,
                     __setattr__=setattr_, __delattr__=delattr_,
                     __repr__=method('__repr__'))
    return type('Recorder', (), namespace)


def outcome(call):
    """El valor —un iterador se consume— o el NOMBRE de la excepción."""
    try:
        result = call()
    except Exception as error:
        return ('raises', type(error).__name__)
    if hasattr(result, '__next__'):
        return ('iterates', list(result))
    return ('value', result)


def run(module, recorder, name):
    """Invoca ``name`` sobre un ``lazy`` nuevo; devuelve resultado y registros.

    El otro operando de un método binario es OTRO registrador, no un número:
    con ``5``, ``int`` devuelve ``NotImplemented`` y Python refleja la llamada
    sobre el valor, así que ``other > value`` y ``value < other`` dejarían el
    mismo registro. Con dos registradores se ve a quién se preguntó.
    """
    value, other = recorder(), recorder()
    proxy = module.lazy(lambda: value)
    method = getattr(type(proxy), name)
    if name in UNARY:
        args = ()
    else:
        args = ARGUMENTS.get(name, (other,))
    result = outcome(lambda: method(proxy, *args))
    return (label(result, value, other), label(value.log, value, other),
            label(other.log, value, other))


def label(data, value, other):
    """Sustituye los registradores por su papel antes de comparar.

    Comparar un registro que los contiene invocaría su propio ``__eq__``, que
    devuelve una ficha verdadera: toda comparación saldría igual.
    """
    if data is value:
        return '<value>'
    if data is other:
        return '<other>'
    if isinstance(data, (list, tuple)):
        return tuple(label(item, value, other) for item in data)
    return data


class TestLazyDelegatesLikeTheReference:
    """Cada método de ``lazy`` delega igual que el de la fuente."""

    def test_it_declares_the_same_methods(self, reference):
        assert delegated_names(ported) == delegated_names(reference)
        assert ported.lazy.__slots__ == reference.lazy.__slots__
        assert isinstance(vars(ported.lazy)['_value'], property)

    def test_every_special_method_delegates_the_same_way(self, reference):
        names = delegated_names(reference)
        recorder = recorder_class(names)
        divergences = []
        for name in names:
            expected = run(reference, recorder, name)
            actual = run(ported, recorder, name)
            if expected != actual:
                divergences.append((name, expected, actual))
        assert len(names) >= 80
        assert not divergences, (
            f'{len(divergences)} de {len(names)} métodos divergen; '
            f'los tres primeros: {divergences[:3]}')

    @pytest.mark.parametrize('name, args', [
        ('__getattr__', ('foo',)),
        ('__setattr__', ('foo', 1)),
        ('__delattr__', ('foo',)),
    ])
    def test_attribute_access_reaches_the_value(self, reference, name, args):
        recorder = recorder_class(delegated_names(reference))
        logs = []
        for module in (reference, ported):
            value = recorder()
            proxy = module.lazy(lambda value=value: value)
            result = outcome(lambda: getattr(type(proxy), name)(proxy, *args))
            logs.append((result, value.log))
        assert logs[0] == logs[1]

    def test_repr_waits_for_the_evaluation(self, reference):
        recorder = recorder_class(delegated_names(reference))
        shapes = []
        for module in (reference, ported):
            calls = []
            proxy = module.lazy(lambda: calls.append(1) or recorder())
            repr(proxy)
            before = len(calls)
            proxy + 0
            proxy + 0
            shapes.append((before, len(calls), repr(proxy)))
        assert shapes[0] == shapes[1]
        assert shapes[1][:2] == (0, 1)


class TestTheDescriptorsMatchTheReference:
    """``lazy_property``, ``classproperty`` y ``lazy_classproperty``."""

    def test_lazy_property_warns_and_caches_as_the_reference(self, reference):
        observed = []
        for module in (reference, ported):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')

                class Holder:
                    @module.lazy_property
                    def answer(self):
                        self.calls += 1
                        return 42

                    def __init__(self):
                        self.calls = 0

                holder = Holder()
                first = (holder.answer, holder.answer, holder.calls)
                module.lazy_property.reset_all(holder)
                second = (holder.answer, holder.calls)
            observed.append((first, second,
                             [(w.category, str(w.message)) for w in caught]))
        assert observed[0] == observed[1]
        assert observed[1][0] == (42, 42, 1)

    def test_classproperty_reads_through_the_class(self, reference):
        observed = []
        for module in (reference, ported):
            class Owner:
                base = 3

                @module.classproperty
                def tripled(cls):
                    """El triple de ``base``."""
                    return cls.base * 3

            class Child(Owner):
                base = 4

            descriptor = vars(Owner)['tripled']
            observed.append((Owner.tripled, Child.tripled, Owner().tripled,
                             descriptor.__doc__))
        assert observed[0] == observed[1]
        assert observed[1] == (9, 12, 9, 'El triple de ``base``.')

    def test_lazy_classproperty_stores_the_value_on_the_owner(self, reference):
        observed = []
        for module in (reference, ported):
            calls = []

            class Owner:
                @module.lazy_classproperty
                def value(cls):
                    calls.append(cls.__name__)
                    return len(calls)

            first, second = Owner.value, Owner.value
            observed.append((first, second, calls,
                             isinstance(vars(Owner)['value'], int)))
        assert observed[0] == observed[1]
        assert observed[1] == (1, 1, ['Owner'], True)


class TestLazyLiterally:
    """Tres casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_less_than_asks_the_other_operand(self):
        # El valor envuelto TAMBIÉN sabe responder: si no, Python reflejaría
        # ``value < other`` sobre ``other.__gt__`` y las dos formas se
        # confundirían.
        class Value:
            def __lt__(self, other):
                return 'answered by the value'

        class Other:
            def __gt__(self, value):
                return 'answered by the other operand'

        answer = ported.lazy(Value) < Other()
        assert answer == 'answered by the other operand'

    def test_in_place_addition_mutates_the_wrapped_list(self):
        items = [1]
        proxy = ported.lazy(lambda: items)
        proxy += [2]
        assert items == [1, 2]

    def test_the_function_runs_once(self):
        calls = []
        proxy = ported.lazy(lambda: calls.append(1) or 10)
        assert proxy + 1 == 11
        assert proxy * 2 == 20
        assert calls == [1]
