"""``tools.facade`` — el proxy que expone un subconjunto de lo envuelto.

Implementa el patron Facade: una clase que delega en una instancia interna y
publica **solo** los atributos y metodos que declara, con casteo opcional del
valor devuelto.

Los casos se escribieron ANTES del modulo. Cubren las tres formas que
``ProxyFunc`` distingue —``staticmethod``, ``classmethod`` y metodo de
instancia— por sus tres ramas de casteo (sin casteo, con casteo, y
``cast=None``, que descarta el valor).
"""
import pytest

from tools.facade import Proxy, ProxyAttr, ProxyFunc


class Engine:
    """Lo envuelto: tiene mas superficie de la que la fachada publica."""

    #: Lo que la fachada NO publica; el control de que el filtro filtra.
    secret = 'no sale'

    def __init__(self, size=3):
        self.size = size
        self.label = None

    def double(self, extra=0):
        return self.size * 2 + extra

    def mutate(self, size):
        self.size = size
        return 'devuelve algo que se descarta'

    @staticmethod
    def add(a, b):
        return a + b

    @classmethod
    def named(cls):
        return 'Engine'

    def __repr__(self):
        return f'Engine({self.size})'

    def __str__(self):
        return f'engine de {self.size}'


class EngineProxy(Proxy):
    """La fachada: publica cuatro cosas de las siete que Engine tiene."""

    _wrapped__ = Engine

    size = ProxyAttr(cast=int)
    label = ProxyAttr()
    double = ProxyFunc(cast=str)
    mutate = ProxyFunc(cast=None)
    add = ProxyFunc()
    named = ProxyFunc()


@pytest.fixture
def facade():
    return EngineProxy(Engine(size=5))


class TestAttribute:
    def test_it_reads_through_with_its_cast(self):
        assert EngineProxy(Engine(size=5)).size == 5

    def test_the_cast_applies(self):
        engine = Engine(size='7')
        assert EngineProxy(engine).size == 7
        assert isinstance(EngineProxy(engine).size, int)

    def test_the_none_survives_the_cast(self):
        """``cast(value) if value is not None else None`` — no castea None."""
        assert EngineProxy(Engine()).label is None

    def test_it_writes_through(self, facade):
        facade.size = 9
        assert facade._wrapped__.size == 9

    def test_what_is_not_declared_does_not_exist(self, facade):
        """El control del filtro: sin este caso la fachada podria estar
        exponiendo todo y las pruebas de arriba pasarian igual."""
        with pytest.raises(AttributeError):
            facade.secret


class TestInstanceMethod:
    def test_it_delegates_with_its_arguments(self, facade):
        assert facade.double(extra=1) == '11'

    def test_the_cast_none_discards_the_value(self, facade):
        """``cast=None`` llama y devuelve ``None``, no lo que el metodo dio."""
        assert facade.mutate(8) is None
        assert facade._wrapped__.size == 8

    def test_it_keeps_the_wrapped_signature(self):
        """``functools.update_wrapper`` conserva nombre y docstring."""
        assert EngineProxy.double.__name__ == 'double'


class TestStaticAndClassMethod:
    def test_the_static_one_stays_static(self, facade):
        assert facade.add(2, 3) == 5
        assert EngineProxy.add(2, 3) == 5

    def test_the_class_one_stays_a_class_method(self, facade):
        assert facade.named() == 'Engine'
        assert EngineProxy.named() == 'Engine'


class TestMeta:
    def test_repr_and_str_come_for_free(self, facade):
        """``ProxyMeta`` los añade cuando la clase no los declara."""
        assert repr(facade) == 'Engine(5)'
        assert str(facade) == 'engine de 5'

    def test_it_impersonates_the_wrapped_class(self, facade):
        """La ``property __class__`` hace que ``isinstance`` diga que si."""
        assert facade.__class__ is Engine
        assert isinstance(facade, Engine)

    def test_the_class_keeps_the_wrapped_identity(self):
        assert EngineProxy.__name__ == 'Engine'
        assert EngineProxy.__doc__ == Engine.__doc__

    def test_the_dict_is_not_copied(self):
        """``updated=[]``: la fachada NO hereda el ``__dict__`` de lo envuelto,
        que es lo que la dejaria exponer ``secret`` por la puerta de atras."""
        assert 'secret' not in EngineProxy.__dict__
