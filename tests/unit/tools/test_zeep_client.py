"""La frontera de serialización de ``tools.zeep`` — el envoltorio de ``zeep``.

Adaptación de ``odoo/tools/zeep/client.py`` (``odoo19c``). El envoltorio no es
azúcar: es lo único que impide que un grafo de objetos construido a partir del
XML de un servicio remoto entre al proceso tal cual.

Cada control de este archivo declara qué lo haría fallar, y se ejerce contra
eso — ``metrica-decide-la-conclusion.md``, sub-patrón D. Un test que siga verde
con la guarda retirada mide otra cosa; los de aquí se miden con
``scripts/neutralize_and_measure.sh``.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import zeep as zeep_lib

from tools import zeep
from tools.zeep.client import (
    SERIALIZABLE_TYPES,
    TIMEOUT,
    Client,
    ReadOnlyMethodNamespace,
    SerialProxy,
)

# El nombre mangleado del serializador privado: la clase lo declara con dos
# guiones bajos, así que se llega por su forma resuelta y no por un alias.
serialize = Client._Client__serialize_object


class TestTheFacadeExposesWhatTheSourceExposes:
    """Los siete símbolos que ``__init__`` reexporta, y el techo de espera."""

    def test_the_package_reexports_the_seven_names_of_the_source(self):
        for name in ('Client', 'Plugin', 'Settings', 'Transport',
                     'exceptions', 'ns', 'wsdl'):
            assert hasattr(zeep, name), name

    def test_the_timeout_is_thirty_seconds_like_the_source(self):
        assert TIMEOUT == 30


class TestTheSerializationBoundaryRejectsWhatItCannotName:
    """``__serialize_object`` deja pasar los tipos declarados y nada más."""

    @pytest.mark.parametrize('value', [
        None, True, 3, 3.5, 'texto', b'bytes', Decimal('1.5'),
        date(2026, 1, 1), datetime(2026, 1, 1), timedelta(seconds=1),
    ])
    def test_a_declared_type_crosses_untouched(self, value):
        assert serialize(value) == value

    def test_an_undeclared_type_raises_instead_of_crossing(self):
        """El control que puede fallar: un objeto cualquiera NO entra.

        Es la conducta que define la frontera. Si ``__serialize_object``
        dejara de levantar, un grafo remoto entraría al proceso y este caso
        sería el único en rojo.
        """
        class Remote:
            pass

        with pytest.raises(ValueError, match='is not serializable'):
            serialize(Remote())

    def test_a_set_is_not_serializable_either(self):
        # ``set`` no está en SERIALIZABLE_TYPES aunque ``tuple`` y ``list`` sí:
        # el criterio es la lista declarada, no "parece una colección".
        assert set not in SERIALIZABLE_TYPES
        with pytest.raises(ValueError, match='is not serializable'):
            serialize({1, 2})

    def test_a_dict_becomes_a_read_only_proxy_recursively(self):
        output = serialize({'a': 1, 'b': {'c': 'x'}})
        assert isinstance(output, SimpleNamespace)
        assert output['a'] == 1
        assert output['b']['c'] == 'x'

    def test_a_list_is_serialized_element_by_element(self):
        assert serialize([1, {'a': 2}])[1]['a'] == 2

    def test_a_nested_undeclared_type_also_raises(self):
        with pytest.raises(ValueError, match='is not serializable'):
            serialize({'a': object()})


class TestTheProxyPassesForACompoundValue:
    """``SerialProxy`` miente su ``__class__`` a propósito, y es su razón de ser."""

    def test_it_reports_the_class_zeep_expects(self):
        # Sin esto, ``zeep.helpers.serialize_object`` no lo reconoce al
        # enviarlo dentro de la carga útil de una petición.
        assert SerialProxy(a=1).__class__ is zeep_lib.xsd.valueobjects.CompoundValue

    def test_it_refuses_a_key_with_a_leading_underscore(self):
        with pytest.raises(AssertionError):
            SerialProxy(_privado=1)

    def test_it_admits_the_value_key_of_the_source(self):
        # ``_value_1`` es la convención de zeep para el contenido simple.
        assert SerialProxy(_value_1='x')['_value_1'] == 'x'

    def test_it_refuses_an_undeclared_type_on_construction(self):
        with pytest.raises(AssertionError):
            SerialProxy(a=object())

    def test_it_refuses_an_undeclared_type_on_assignment(self):
        proxy = SerialProxy(a=1)
        with pytest.raises(AssertionError):
            proxy.a = object()

    def test_setitem_is_refused_while_setattr_is_allowed(self):
        proxy = SerialProxy(a=1)
        proxy.a = 2                       # permitido: la fuente lo permite
        assert proxy['a'] == 2
        with pytest.raises(NotImplementedError):
            proxy['a'] = 3

    def test_it_behaves_as_a_mapping_for_zeep(self):
        proxy = SerialProxy(a=1, b='x')
        assert sorted(proxy) == ['a', 'b']
        assert sorted(proxy.keys()) == ['a', 'b']
        assert dict(proxy.items()) == {'a': 1, 'b': 'x'}
        del proxy['a']
        assert 'a' not in proxy.keys()


class TestTheNamespaceIsReadOnly:
    """``ReadOnlyMethodNamespace`` es el que devuelven ``service`` y ``bind``."""

    def test_setattr_and_delattr_are_refused(self):
        namespace = ReadOnlyMethodNamespace(operacion=lambda: None)
        with pytest.raises(NotImplementedError):
            namespace.operacion = lambda: None
        with pytest.raises(NotImplementedError):
            del namespace.operacion

    def test_it_admits_only_public_functions(self):
        with pytest.raises(AssertionError):
            ReadOnlyMethodNamespace(_privada=lambda: None)
        with pytest.raises(AssertionError):
            ReadOnlyMethodNamespace(dato=1)

    def test_binding_options_is_the_only_underscore_key_admitted(self):
        # ``bind`` la añade; es la excepción que la fuente declara.
        namespace = ReadOnlyMethodNamespace(op=lambda: None, _binding_options={'address': 'x'})
        assert namespace['_binding_options'] == {'address': 'x'}


class TestTheTimeoutsAreSetHereAndNotInheritedFromTheRemote:
    """``Client.__init__`` fija los dos techos y la sesión antes de construir."""

    @pytest.fixture
    def zeep_client_spy(self, monkeypatch):
        """Sustituye ``zeep.Client`` para no ir a la red por un WSDL."""
        captured = {}

        def fake(*args, **kwargs):
            captured['args'] = args
            captured['kwargs'] = kwargs
            return SimpleNamespace(service=SimpleNamespace(_operations={}))

        monkeypatch.setattr(zeep_lib, 'Client', fake)
        return captured

    def test_the_ceiling_only_floors_the_operation_timeout(self, zeep_client_spy):
        """``TIMEOUT`` es piso de la operación, no de la carga — medido.

        La cadena ``kwargs or transport.<x> or TIMEOUT`` de la fuente sólo
        llega a ``TIMEOUT`` cuando el transport no trae value propio. Medido
        sobre ``zeep==4.3.3``: ``Transport()`` nace con ``load_timeout=300`` y
        ``operation_timeout=None``, así que el techo de 30 s gobierna **la
        operación** y la carga del WSDL conserva los 300 s de ``zeep``.

        *Métrica:* los dos atributos del transport tras construir el
        envoltorio sin argumentos.
        *Ciega a:* si un ``zeep`` futuro cambia ese 300 — el caso lo detectaría
        como rojo, que es lo que se quiere.
        """
        Client('http://ejemplo/servicio?wsdl')
        transport = zeep_client_spy['kwargs']['transport']
        assert transport.load_timeout == zeep_lib.Transport().load_timeout
        assert transport.operation_timeout == TIMEOUT

    def test_an_explicit_timeout_wins_over_the_ceiling(self, zeep_client_spy):
        Client('http://ejemplo/servicio?wsdl', timeout=5, operation_timeout=7)
        transport = zeep_client_spy['kwargs']['transport']
        assert transport.load_timeout == 5
        assert transport.operation_timeout == 7

    def test_the_timeout_kwargs_do_not_reach_zeep(self, zeep_client_spy):
        # ``zeep.Client`` no los admite: el envoltorio los consume con ``pop``.
        Client('http://ejemplo/servicio?wsdl', timeout=5, session=object())
        assert 'timeout' not in zeep_client_spy['kwargs']
        assert 'session' not in zeep_client_spy['kwargs']

    def test_an_explicit_session_reaches_the_transport(self, zeep_client_spy):
        session = object()
        Client('http://ejemplo/servicio?wsdl', session=session)
        assert zeep_client_spy['kwargs']['transport'].session is session
