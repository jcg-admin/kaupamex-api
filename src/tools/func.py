"""``tools.func`` — espejo de ``odoo/tools/func.py``, portado entero.

Censo de la fuente (``odoo19c: odoo/tools/func.py``), medido por AST: **diez**
símbolos de API — nueve definiciones (``reset_cached_properties``,
``lazy_property``, ``conditional``, ``filter_kwargs``, ``synchronized``,
``frame_codeinfo``, ``classproperty``, ``lazy_classproperty`` y ``lazy``) más
``locked``, que es un alias de módulo (``:93``: ``locked = synchronized()``).
Fuera del censo quedan los dos parámetros de tipo (``T``, ``P``) y ``__all__``,
que no son API.

**Portados diez de diez.** Hasta 2026-09-03 este archivo llevaba tres y su
docstring declaraba el criterio *"un símbolo llega aquí cuando un módulo
portado lo importa"*. Ese criterio queda **retirado, y no por haber aparecido
un consumidor**: el consumidor no es la condición. Todo símbolo de la
referencia se implementa, y el que hoy no tiene quien lo llame lo tendrá
porque su llamador también se implementa. Esperar al consumidor es la forma
que ``porte-completo-no-parcial.md`` prohíbe — un porte parcial que se
presenta como completo porque su propia regla lo autoriza.

Ejemplo de lo segundo, no de lo primero: ``Registry`` decora sus métodos de
clase con ``@locked`` (``odoo19c: odoo/orm/registry.py:32``). Cuando se porte,
``locked`` ya está aquí; el orden entre los dos no cambia que ambos se portan.

``__all__`` conserva los **seis** nombres que declara la fuente. Los otros
cuatro —``filter_kwargs``, ``synchronized``, ``locked`` y ``frame_codeinfo``—
no están ahí en la referencia y tampoco aquí: se importan por nombre, no por
``from tools.func import *``. Esa asimetría es del original y se preserva.

Adaptado de Odoo Community ``odoo/tools/func.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import functools
import typing
import warnings
from collections.abc import Callable
from inspect import Parameter, getsourcefile, signature

__all__ = [
    'classproperty',
    'conditional',
    'lazy',
    'lazy_classproperty',
    'lazy_property',
    'reset_cached_properties',
]

T = typing.TypeVar('T')
P = typing.ParamSpec('P')


def reset_cached_properties(obj):
    """Vacía las ``functools.cached_property`` memorizadas en ``obj``.

    ≙ ``reset_cached_properties`` (``odoo19c: odoo/tools/func.py:20-26``).
    Docstring de la fuente, verbatim: *"Reset all cached properties on the
    instance `obj`"*.

    Una ``cached_property`` guarda su resultado en el ``__dict__`` de la
    instancia bajo su propio nombre; borrar esa entrada hace que la siguiente
    lectura vuelva a calcular. **Sólo** se borra lo que respalda a una
    ``cached_property`` del tipo: un atributo normal del mismo ``__dict__``
    sobrevive, y ésa es la mitad que hace del guion un control y no un
    ``vars(obj).clear()``.

    Su consumidor aquí es ``Transaction.reset``
    (``odoo19c: odoo/orm/environments.py:610-618``): tras reasignar el
    registro, lo que cada entorno memorizó sobre el registro viejo deja de ser
    válido.
    """
    cls = type(obj)
    obj_dict = vars(obj)
    for name in list(obj_dict):
        if isinstance(getattr(cls, name, None), functools.cached_property):
            del obj_dict[name]


class lazy_property(functools.cached_property):
    """``cached_property`` que avisa de su propia obsolescencia — ≙ ``:32-46``.

    La fuente la marca deprecada desde su versión 19 y remite a
    ``functools.cached_property``, de la que hereda. Se porta **con** el aviso:
    quitarlo convertiría un símbolo en retirada en uno vigente, que es cambiar
    el contrato en vez de portarlo. El nombre va en minúscula porque lo es en
    la fuente — se escribe como un decorador, no como un tipo.

    ``stacklevel=2`` en el ``__init__`` apunta el aviso a la línea que declara
    la propiedad, no a este archivo: quien la declara es quien tiene que verlo.
    """

    def __init__(self, func):
        super().__init__(func)
        warnings.warn(
            "lazy_property is deprecated since Odoo 19, use `functools.cached_property`",
            category=DeprecationWarning,
            stacklevel=2,
        )

    @staticmethod
    def reset_all(instance):
        """Vacía todas las propiedades memorizadas de ``instance``.

        Delega en ``reset_cached_properties``, que es lo que la fuente pide
        llamar directamente.
        """
        warnings.warn(
            "lazy_property is deprecated since Odoo 19, use `reset_cache_properties` directly",
            category=DeprecationWarning,
        )
        reset_cached_properties(instance)


def conditional(condition: typing.Any, decorator: Callable[[T], T]) -> Callable[[T], T]:
    """Aplica ``decorator`` sólo si ``condition`` es verdadera — ≙ ``:49-60``.

    Docstring de la fuente, verbatim: *"Decorator for a conditionally applied
    decorator"*, con este ejemplo::

        @conditional(get_config('use_cache'), ormcache)
        def fn():
            pass

    Cuando la condición es falsa devuelve la identidad, no ``None``: el sitio
    de la declaración sigue siendo un decorador válido y la función queda sin
    envolver. Evalúa la **veracidad** del argumento, no su identidad con
    ``True`` — un ``0`` o una cadena vacía desactivan igual.
    """
    if condition:
        return decorator
    else:
        return lambda fn: fn


def filter_kwargs(func: Callable, kwargs: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Recorta ``kwargs`` a lo que la firma de ``func`` acepta — ≙ ``:63-77``.

    Docstring de la fuente, verbatim: *"Filter the given keyword arguments to
    only return the kwargs that binds to the function's signature"*.

    Tres reglas, y las tres salen del recorrido de ``inspect.signature``:

    - un parámetro posicional-o-nombrado y uno sólo-nombrado **retienen** su
      clave;
    - un ``**kwargs`` en la firma retiene **todas** — no hay sobrante posible,
      y por eso el recorrido corta ahí;
    - un parámetro **sólo posicional** no retiene nada: su nombre no se puede
      pasar por palabra clave, así que la clave homónima sobra.

    Devuelve el **mismo objeto** cuando no sobra nada. Es lo que hace la
    fuente y no es cosmético: quien llame puede seguir escribiendo en el dict
    original sin que una copia intermedia se lo trague.
    """
    leftovers = set(kwargs)
    for p in signature(func).parameters.values():
        if p.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY):
            leftovers.discard(p.name)
        elif p.kind == Parameter.VAR_KEYWORD:
            leftovers.clear()
            break

    if not leftovers:
        return kwargs

    return {key: kwargs[key] for key in kwargs if key not in leftovers}


def synchronized(lock_attr: str = '_lock') -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Envuelve un método en el cerrojo que la instancia lleva — ≙ ``:80-90``.

    El cerrojo **no** lo crea este decorador: lo busca en la instancia por
    nombre de atributo al llamar, no al declarar. Eso permite que cada
    instancia traiga el suyo y que el atributo se asigne después de que la
    clase esté definida.

    Se entra con ``with``, así que el cerrojo se libera también cuando el
    cuerpo levanta una excepción.
    """
    def synchronized_lock(func, /):
        @functools.wraps(func)
        def locked(inst, *args, **kwargs):
            with getattr(inst, lock_attr):
                return func(inst, *args, **kwargs)
        return locked
    return synchronized_lock


locked = synchronized()
"""El caso corriente de :func:`synchronized`: el cerrojo en ``self._lock``.

≙ ``odoo19c: odoo/tools/func.py:93``. Es un alias de módulo, no una función
propia — se aplica sin llamar (``@locked``), mientras que ``synchronized``
se llama para nombrar otro atributo (``@synchronized('_mi_cerrojo')``).
Su consumidor en el ORM es ``Registry``, que decora con él sus métodos de
clase (``odoo19c: odoo/orm/registry.py:32``).
"""


def frame_codeinfo(fframe, back=0):
    """Devuelve ``(archivo, linea)`` de un marco anterior — ≙ ``:96-111``.

    Docstring de la fuente, verbatim: *"Return a (filename, line) pair for a
    previous frame. @return (filename, lineno) where lineno is either int or
    string==''"*.

    Es un guion de diagnóstico, así que **traga cualquier excepción** y
    devuelve ``("<unknown>", '')``. Esa forma no es descuido: quien lo llama
    está construyendo un mensaje de error, y un fallo aquí no puede tapar el
    error que se estaba reportando.

    Dos variantes del par vacío, ambas de la fuente: ``"<unknown>"`` cuando no
    hay marco o algo falla, y ``'<builtin>'`` cuando el marco existe pero no
    tiene archivo fuente. El número de línea sale ``''`` —cadena, no cero—
    cuando el marco no lo declara.
    """
    try:
        if not fframe:
            return "<unknown>", ''
        for _i in range(back):
            fframe = fframe.f_back
        try:
            fname = getsourcefile(fframe)
        except TypeError:
            fname = '<builtin>'
        lineno = fframe.f_lineno or ''
        return fname, lineno
    except Exception:
        return "<unknown>", ''


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


class lazy_classproperty(classproperty[T], typing.Generic[T]):
    """``classproperty`` que se sustituye a sí misma tras el primer cálculo.

    ≙ ``odoo19c: odoo/tools/func.py:127-131``. Docstring de la fuente,
    verbatim: *"Similar to :class:`lazy_property`, but for classes"*.

    La memorización no es un diccionario aparte: el descriptor **se borra** al
    asignar el valor sobre el dueño con el mismo nombre. La segunda lectura ya
    no pasa por aquí — encuentra un atributo de clase normal. De ahí que el
    valor se guarde bajo ``self.fget.__name__``: el nombre de la función
    decorada es el nombre bajo el que la clase la declara.

    Sustituye en el **dueño**, no en la clase por la que se pregunta. Con
    herencia, leerla desde una subclase memoriza en la clase que la declara.
    """

    def __get__(self, cls, owner=None, /):
        val = super().__get__(cls, owner)
        setattr(owner, self.fget.__name__, val)
        return val


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
