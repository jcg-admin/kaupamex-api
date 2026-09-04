"""Proxy con patron Facade — adaptacion de ``odoo19c: odoo/tools/facade.py``
(``odoo-tools@622ddc2a``, LGPL-3 segun el ``__manifest__.py`` de su addon
raiz: copia + adaptacion con atribucion preservada, DEC-KX-03).

Que resuelve: envolver una instancia y publicar de ella **solo** los atributos
y metodos que la fachada declara, con casteo opcional del valor devuelto. Es
el mecanismo con que la referencia expone una biblioteca de terceros sin
entregar su superficie entera.

**Se portan 4 de 4 simbolos** (``ProxyAttr``, ``ProxyFunc``, ``ProxyMeta``,
``Proxy``). El archivo aterriza en ``src/tools/`` porque ``src/tools`` ↔
``odoo/tools`` es una raiz espejada.

El stack lo TRAE — no hay nada que construir
=============================================

CPython puro: ``functools`` e ``inspect``. Los tres mecanismos que usa son de
serie —el protocolo ``__set_name__`` del descriptor,
``inspect.getattr_static`` para leer el descriptor sin dispararlo, y
``functools.update_wrapper`` con ``updated=[]`` para copiar la identidad de la
clase envuelta **sin** copiarle el ``__dict__``, que es lo que dejaria pasar
lo no declarado.

Divergencia de mecanismo declarada — ninguna
=============================================

Se porta literal salvo el idioma de docstrings y comentarios. Los nombres con
doble guion bajo al final (``_wrapped__``, ``_cast__``) se conservan: no son
un descuido de la fuente sino la forma de esquivar el *name mangling* de
Python —``__wrapped`` dentro de una clase se reescribiria a
``_Clase__wrapped``— y ademas dejan libre el ``__wrapped__`` que
``functools.update_wrapper`` escribe.
"""
import functools
import inspect


class ProxyAttr:
    """Descriptor que envuelve un atributo de la instancia envuelta.

    Se usa con la clase ``Proxy``: declara que ese atributo es visible desde
    la fachada, con casteo opcional al leerlo.
    """

    def __init__(self, cast=False):
        self._cast__ = cast

    def __set_name__(self, owner, name):
        cast = self._cast__
        if cast:
            def getter(self):
                value = getattr(self._wrapped__, name)
                return cast(value) if value is not None else None
        else:
            def getter(self):
                return getattr(self._wrapped__, name)

        def setter(self, value):
            return setattr(self._wrapped__, name, value)

        setattr(owner, name, property(getter, setter))


class ProxyFunc:
    """Descriptor que envuelve una funcion de la instancia envuelta.

    Se usa con la clase ``Proxy``: declara que esa funcion es visible desde la
    fachada, con casteo opcional del valor devuelto. ``cast=None`` es un
    tercer modo: llama y **descarta** lo que la funcion devuelva.
    """

    def __init__(self, cast=False):
        self._cast__ = cast

    def __set_name__(self, owner, name):
        func = getattr(owner._wrapped__, name)
        # ``getattr_static`` lee el descriptor sin dispararlo: es lo que
        # distingue un staticmethod de un classmethod de un metodo normal.
        descriptor = inspect.getattr_static(owner._wrapped__, name)
        cast = self._cast__

        if isinstance(descriptor, staticmethod):
            if cast:
                def wrap_func(*args, **kwargs):
                    result = func(*args, **kwargs)
                    return cast(result) if result is not None else None
            elif cast is None:
                def wrap_func(*args, **kwargs):
                    func(*args, **kwargs)
            else:
                def wrap_func(*args, **kwargs):
                    return func(*args, **kwargs)

            functools.update_wrapper(wrap_func, func)
            wrap_func = staticmethod(wrap_func)

        elif isinstance(descriptor, classmethod):
            if cast:
                def wrap_func(cls, *args, **kwargs):
                    result = func(*args, **kwargs)
                    return cast(result) if result is not None else None
            elif cast is None:
                def wrap_func(cls, *args, **kwargs):
                    func(*args, **kwargs)
            else:
                def wrap_func(cls, *args, **kwargs):
                    return func(*args, **kwargs)

            functools.update_wrapper(wrap_func, func)
            wrap_func = classmethod(wrap_func)

        else:
            if cast:
                def wrap_func(self, *args, **kwargs):
                    result = func(self._wrapped__, *args, **kwargs)
                    return cast(result) if result is not None else None
            elif cast is None:
                def wrap_func(self, *args, **kwargs):
                    func(self._wrapped__, *args, **kwargs)
            else:
                def wrap_func(self, *args, **kwargs):
                    return func(self._wrapped__, *args, **kwargs)

            functools.update_wrapper(wrap_func, func)

        setattr(owner, name, wrap_func)


class ProxyMeta(type):
    """Metaclase de la fachada: añade la representacion y copia la identidad."""

    def __new__(cls, clsname, bases, attrs):
        attrs.update({
            func: ProxyFunc()
            for func in ("__repr__", "__str__")
            if func not in attrs
        })
        proxy_class = super().__new__(cls, clsname, bases, attrs)
        # Para preservar el docstring, la firma y el codigo de la clase
        # envuelta. ``updated`` va a lista vacia para que NO copie el
        # ``__dict__``. Ver ``functools.WRAPPER_ASSIGNMENTS`` y
        # ``functools.WRAPPER_UPDATES``.
        functools.update_wrapper(proxy_class, proxy_class._wrapped__, updated=[])
        return proxy_class


class Proxy(metaclass=ProxyMeta):
    """Clase proxy que implementa el patron Facade.

    Delega en una instancia subyacente exponiendo un subconjunto curado de sus
    atributos y metodos. Sirve para controlar el acceso, simplificar una
    interfaz o añadir asuntos transversales.
    """

    _wrapped__ = object

    def __init__(self, instance):
        """Inicializa el proxy fijando la instancia envuelta.

        :param instance: la instancia de la clase que se envuelve.
        """
        object.__setattr__(self, "_wrapped__", instance)

    @property
    def __class__(self):
        return type(self)._wrapped__
