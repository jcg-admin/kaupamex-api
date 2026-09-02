"""``tools.func`` — espejo de ``odoo/tools/func.py`` (sólo símbolos con consumidor).

Misma regla que ``tools/misc.py``: un símbolo llega aquí cuando un módulo
portado lo importa (``from tools.func import X``, espejo de ``from odoo.tools
import X``), y **antes de portarlo se decide** si el stdlib ya lo resuelve. La
decisión queda en el docstring del símbolo — no se porta por completitud.

Censo de la fuente (``odoo19c: odoo/tools/func.py``), medido por AST: **diez**
símbolos de API — nueve definiciones (``reset_cached_properties``,
``lazy_property``, ``conditional``, ``filter_kwargs``, ``synchronized``,
``frame_codeinfo``, ``classproperty``, ``lazy_classproperty`` y ``lazy``) más
``locked``, que es un alias de módulo (``:93``: ``locked = synchronized()``).
Fuera del censo quedan los dos parámetros de tipo (``T``, ``P``) y ``__all__``,
que no son API.

Portados **dos**:

- ``classproperty`` (``:115-125``), que ``orm/domains.py`` consume;
- ``lazy`` (``:135-262``), que ``tools/json.py`` consume en la tercera rama de
  ``json_default`` — tarea #142.

**Ausentes: ocho** —``reset_cached_properties``, ``lazy_property``,
``conditional``, ``filter_kwargs``, ``synchronized``, ``locked``,
``frame_codeinfo`` y ``lazy_classproperty``—; ninguno tiene consumidor en este
árbol y su porte se decide cuando lo tenga. Cuatro de ellos —``filter_kwargs``,
``synchronized``, ``locked`` y ``frame_codeinfo``— ni siquiera están en el
``__all__`` de la fuente, que declara seis nombres.

Adaptado de Odoo Community ``odoo/tools/func.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import typing

__all__ = ['classproperty', 'lazy']

T = typing.TypeVar('T')


class classproperty(typing.Generic[T]):
    """Una ``property`` que se resuelve sobre la clase — ≙ ``func.py:115-125``.

    ``orm/domains.py`` la consume en tres sitios: ``Domain.TRUE``,
    ``Domain.FALSE`` y ``DomainNary.INVERSE``. Los tres devuelven objetos que
    sólo existen **después** del cuerpo de la clase que los declara —los dos
    singletons ``DomainBool`` y la clase hermana ``DomainAnd``/``DomainOr``—,
    así que un atributo de clase normal no puede declararlos donde la fuente
    los declara.

    Python no la trae. Encadenar ``@classmethod`` con ``@property`` funcionaba
    en 3.9-3.10 y quedó **retirado en 3.11**; este proyecto corre 3.12+
    (``pyproject.toml``), así que ese camino no existe. De ahí que se porte en
    vez de aliasarse.
    """

    def __init__(self, fget):
        self.fget = classmethod(fget)

    def __get__(self, cls, owner=None, /):
        return self.fget.__get__(None, owner)()

    @property
    def __doc__(self):
        return self.fget.__doc__


class lazy:
    """Proxy al resultado (memoizado) de una evaluación diferida — ≙ ``:135-262``.

    .. code-block::

        foo = lazy(func, arg)           # func(arg) todavía no se llama
        bar = foo + 1                   # evalúa func(arg) y suma 1
        baz = foo + 2                   # reusa el resultado y suma 2

    El nombre va en minúscula porque lo es en la fuente: se escribe como si
    fuera una función y su llamada construye el proxy. Se conserva verbatim.

    Python no lo trae. ``functools.cached_property`` difiere el cálculo pero
    vive en una clase y devuelve el valor pelado; un ``lambda`` lo difiere y
    obliga al consumidor a llamarlo. Ninguno de los dos es un **proxy**: aquí
    el objeto se usa como si fuera el valor —se suma, se itera, se compara, se
    le piden atributos— y el cálculo ocurre en el primer uso, una sola vez.
    Esa es la propiedad que ``json_default`` explota para serializar el valor
    envuelto sin haber tenido que evaluarlo antes.

    La fuente declara ``class lazy(object)``, herencia explícita que en Python
    3 no cambia nada; aquí se omite la base redundante y no la conducta.
    """
    __slots__ = ['_func', '_args', '_kwargs', '_cached_value']

    def __init__(self, func, *args, **kwargs):
        # se salta el ``__setattr__`` propio, que escribiría en el valor
        object.__setattr__(self, '_func', func)
        object.__setattr__(self, '_args', args)
        object.__setattr__(self, '_kwargs', kwargs)

    @property
    def _value(self):
        """El valor, calculándolo la primera vez y soltando lo que lo produjo.

        Poner los tres campos en ``None`` no es limpieza cosmética: mantener la
        referencia al llamable y a sus argumentos alargaría su vida tanto como
        la del proxy.
        """
        if self._func is not None:
            value = self._func(*self._args, **self._kwargs)
            object.__setattr__(self, '_func', None)
            object.__setattr__(self, '_args', None)
            object.__setattr__(self, '_kwargs', None)
            object.__setattr__(self, '_cached_value', value)
        return self._cached_value

    def __getattr__(self, name): return getattr(self._value, name)
    def __setattr__(self, name, value): return setattr(self._value, name, value)
    def __delattr__(self, name): return delattr(self._value, name)

    def __repr__(self):
        # sin evaluar, el ``repr`` de un objeto cualquiera: pedirlo desde un
        # depurador no debe disparar el cálculo que el proxy existe para diferir
        return repr(self._value) if self._func is None else object.__repr__(self)

    def __str__(self): return str(self._value)
    def __bytes__(self): return bytes(self._value)
    def __format__(self, format_spec): return format(self._value, format_spec)

    def __lt__(self, other): return other > self._value
    def __le__(self, other): return other >= self._value
    def __eq__(self, other): return other == self._value
    def __ne__(self, other): return other != self._value
    def __gt__(self, other): return other < self._value
    def __ge__(self, other): return other <= self._value

    def __hash__(self): return hash(self._value)
    def __bool__(self): return bool(self._value)

    def __call__(self, *args, **kwargs): return self._value(*args, **kwargs)

    def __len__(self): return len(self._value)
    def __getitem__(self, key): return self._value[key]
    def __missing__(self, key): return self._value.__missing__(key)
    def __setitem__(self, key, value): self._value[key] = value
    def __delitem__(self, key): del self._value[key]
    def __iter__(self): return iter(self._value)
    def __reversed__(self): return reversed(self._value)
    def __contains__(self, key): return key in self._value

    def __add__(self, other): return self._value.__add__(other)
    def __sub__(self, other): return self._value.__sub__(other)
    def __mul__(self, other): return self._value.__mul__(other)
    def __matmul__(self, other): return self._value.__matmul__(other)
    def __truediv__(self, other): return self._value.__truediv__(other)
    def __floordiv__(self, other): return self._value.__floordiv__(other)
    def __mod__(self, other): return self._value.__mod__(other)
    def __divmod__(self, other): return self._value.__divmod__(other)
    def __pow__(self, other): return self._value.__pow__(other)
    def __lshift__(self, other): return self._value.__lshift__(other)
    def __rshift__(self, other): return self._value.__rshift__(other)
    def __and__(self, other): return self._value.__and__(other)
    def __xor__(self, other): return self._value.__xor__(other)
    def __or__(self, other): return self._value.__or__(other)

    def __radd__(self, other): return self._value.__radd__(other)
    def __rsub__(self, other): return self._value.__rsub__(other)
    def __rmul__(self, other): return self._value.__rmul__(other)
    def __rmatmul__(self, other): return self._value.__rmatmul__(other)
    def __rtruediv__(self, other): return self._value.__rtruediv__(other)
    def __rfloordiv__(self, other): return self._value.__rfloordiv__(other)
    def __rmod__(self, other): return self._value.__rmod__(other)
    def __rdivmod__(self, other): return self._value.__rdivmod__(other)
    def __rpow__(self, other): return self._value.__rpow__(other)
    def __rlshift__(self, other): return self._value.__rlshift__(other)
    def __rrshift__(self, other): return self._value.__rrshift__(other)
    def __rand__(self, other): return self._value.__rand__(other)
    def __rxor__(self, other): return self._value.__rxor__(other)
    def __ror__(self, other): return self._value.__ror__(other)

    def __iadd__(self, other): return self._value.__iadd__(other)
    def __isub__(self, other): return self._value.__isub__(other)
    def __imul__(self, other): return self._value.__imul__(other)
    def __imatmul__(self, other): return self._value.__imatmul__(other)
    def __itruediv__(self, other): return self._value.__itruediv__(other)
    def __ifloordiv__(self, other): return self._value.__ifloordiv__(other)
    def __imod__(self, other): return self._value.__imod__(other)
    def __ipow__(self, other): return self._value.__ipow__(other)
    def __ilshift__(self, other): return self._value.__ilshift__(other)
    def __irshift__(self, other): return self._value.__irshift__(other)
    def __iand__(self, other): return self._value.__iand__(other)
    def __ixor__(self, other): return self._value.__ixor__(other)
    def __ior__(self, other): return self._value.__ior__(other)

    def __neg__(self): return self._value.__neg__()
    def __pos__(self): return self._value.__pos__()
    def __abs__(self): return self._value.__abs__()
    def __invert__(self): return self._value.__invert__()

    def __complex__(self): return complex(self._value)
    def __int__(self): return int(self._value)
    def __float__(self): return float(self._value)

    def __index__(self): return self._value.__index__()

    def __round__(self): return self._value.__round__()
    def __trunc__(self): return self._value.__trunc__()
    def __floor__(self): return self._value.__floor__()
    def __ceil__(self): return self._value.__ceil__()

    def __enter__(self): return self._value.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        return self._value.__exit__(exc_type, exc_value, traceback)

    def __await__(self): return self._value.__await__()
    def __aiter__(self): return self._value.__aiter__()
    def __anext__(self): return self._value.__anext__()
    def __aenter__(self): return self._value.__aenter__()

    def __aexit__(self, exc_type, exc_value, traceback):
        return self._value.__aexit__(exc_type, exc_value, traceback)
