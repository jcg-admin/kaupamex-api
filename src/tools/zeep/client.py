"""``Client`` — la fachada estrecha sobre ``zeep.Client``.

Adaptación de ``odoo/tools/zeep/client.py`` (``odoo19c``, LGPL-3: copia +
adaptación con atribución).

**No es azúcar: es una frontera de seguridad.** ``zeep`` devuelve grafos de
objetos ``CompoundValue`` construidos a partir del XML que responde un
servicio remoto. Dejar que ese grafo cruce hacia el ORM es dejar que un
tercero decida qué tipos entran en el proceso. La fachada hace tres cosas, y
las tres son restricciones:

1. **Serializa lo devuelto** — todo valor pasa por ``SERIALIZABLE_TYPES``, y
   lo que no es de esos tipos levanta ``ValueError`` en vez de entrar.
2. **Restringe la superficie** — expone ``service``, ``type_factory``,
   ``get_type``, ``create_service`` y ``bind``, no el cliente entero.
3. **Devuelve espacios de nombres de sólo lectura** — ``__setattr__`` y
   ``__delattr__`` levantan ``NotImplementedError``.

Los tiempos de espera se fijan aquí y no se heredan del servicio remoto:
``TIMEOUT`` = 30 s tanto para cargar el WSDL/XSD como para cada operación.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import FunctionType, SimpleNamespace

import zeep
from requests import Response

TIMEOUT = 30
SERIALIZABLE_TYPES = (
    type(None), bool, int, float, str, bytes, tuple, list, dict, Decimal,
    date, datetime, timedelta, Response,
)


class Client:
    """Envoltorio de ``zeep.Client``.

    Ofrece un API más simple para pasar tiempos de espera y sesión, acota sus
    atributos a los que el árbol usa, y serializa lo que devuelven sus
    métodos.
    """

    def __init__(self, *args, **kwargs):
        transport = kwargs.setdefault('transport', zeep.Transport())
        # El tiempo de espera al cargar los documentos WSDL y XSD.
        transport.load_timeout = (
            kwargs.pop('timeout', None) or transport.load_timeout or TIMEOUT
        )
        # El tiempo de espera de cada operación (POST/GET).
        transport.operation_timeout = (
            kwargs.pop('operation_timeout', None)
            or transport.operation_timeout
            or TIMEOUT
        )
        # La ``requests.session`` con que se hacen las peticiones HTTP.
        transport.session = kwargs.pop('session', None) or transport.session

        client = zeep.Client(*args, **kwargs)

        self.__obj = client
        self.__service = None

    @classmethod
    def __serialize_object(cls, obj):
        if isinstance(obj, list):
            return [cls.__serialize_object(sub) for sub in obj]
        if isinstance(obj, (dict, zeep.xsd.valueobjects.CompoundValue)):
            return SerialProxy(**{
                key: cls.__serialize_object(obj[key]) for key in obj
            })
        if type(obj) in SERIALIZABLE_TYPES:
            return obj
        raise ValueError(f'{obj} is not serializable')

    @classmethod
    def __serialize_object_wrapper(cls, method):
        def wrapper(*args, **kwargs):
            return cls.__serialize_object(method(*args, **kwargs))
        return wrapper

    @property
    def service(self):
        if not self.__service:
            self.__service = ReadOnlyMethodNamespace(**{
                key: self.__serialize_object_wrapper(operation)
                for key, operation in self.__obj.service._operations.items()
            })
        return self.__service

    def type_factory(self, namespace):
        types = self.__obj.wsdl.types
        namespace = (
            namespace if namespace in types.namespaces
            else types.get_ns_prefix(namespace)
        )
        documents = types.documents.get_by_namespace(namespace, fail_silently=True)
        types = {
            key[len(f'{{{namespace}}}'):]: type_
            for document in documents
            for key, type_ in document._types.items()
        }
        return ReadOnlyMethodNamespace(**{
            key: self.__serialize_object_wrapper(type_)
            for key, type_ in types.items()
        })

    def get_type(self, name):
        return self.__serialize_object_wrapper(self.__obj.wsdl.types.get_type(name))

    def create_service(self, binding_name, address):
        service = self.__obj.create_service(binding_name, address)
        return ReadOnlyMethodNamespace(**{
            key: self.__serialize_object_wrapper(operation)
            for key, operation in service._operations.items()
        })

    def bind(self, service_name, port_name):
        service = self.__obj.bind(service_name, port_name)
        operations = {
            key: self.__serialize_object_wrapper(operation)
            for key, operation in service._operations.items()
        }
        operations['_binding_options'] = service._binding_options
        return ReadOnlyMethodNamespace(**operations)


class ReadOnlyMethodNamespace(SimpleNamespace):
    """Espacio de nombres de sólo lectura, sin claves con guion bajo y acotado
    a funciones.

    ``types.SimpleNamespace`` no implementa ``__setitem__`` ni ``__delitem__``,
    así que no hace falta implementarlos para que la clase sea de sólo lectura.
    """

    def __init__(self, **kwargs):
        assert all(
            (not key.startswith('_') and isinstance(value, FunctionType))
            or
            (key == '_binding_options' and isinstance(value, dict))
            for key, value in kwargs.items()
        )
        super().__init__(**kwargs)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setattr__(self, key, value):
        raise NotImplementedError

    def __delattr__(self, key):
        raise NotImplementedError


class SerialProxy(SimpleNamespace):
    """Espacio de nombres sin claves con guion bajo y acotado a pocos tipos.

    Se hace pasar por un ``CompoundValue`` de ``zeep`` para que
    ``zeep.helpers.serialize_object`` lo trate como tal.

    Admite ``__getitem__`` y ``__delitem__``; ``__setitem__`` está impedido::

        proxy = SerialProxy(foo='foo')
        proxy.foo         # permitido
        proxy['foo']      # permitido
        proxy.foo = 'bar' # permitido
        proxy['foo'] = 'bar'  # impedido
        del proxy.foo     # permitido
        del proxy['foo']  # permitido
    """

    # Se hace pasar por un CompoundValue para que zeep lo pueda serializar al
    # enviarlo dentro de la carga útil de una petición.
    # https://stackoverflow.com/a/42958013
    @property
    def __class__(self):
        return zeep.xsd.valueobjects.CompoundValue

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            self.__check(key, value)
        super().__init__(**kwargs)

    def __setattr__(self, key, value):
        self.__check(key, value)
        return super().__setattr__(key, value)

    def __getitem__(self, key):
        self.__check(key, None)
        return self.__getattribute__(key)

    # No hace falta —``SimpleNamespace`` no lo implementa— pero se declara
    # para que la prohibición sea explícita.
    def __setitem__(self, key, value):
        raise NotImplementedError

    def __delitem__(self, key):
        self.__check(key, None)
        self.__delattr__(key)

    def __iter__(self):
        return iter(self.__dict__)

    def __repr__(self):
        return repr(self.__dict__)

    def __str__(self):
        return str(self.__dict__)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    @classmethod
    def __check(cls, key, value):
        assert not key.startswith('_') or key.startswith('_value_')
        assert type(value) in SERIALIZABLE_TYPES + (SerialProxy,)
