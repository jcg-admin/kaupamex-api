"""``tools.cache`` — espejo de ``odoo/tools/cache.py`` (Odoo 19).

El decorador de memorización de métodos de modelo, con su contador de
estadísticas y el vaciado por nombre de caché. Se porta porque el stack no
trae el mecanismo: ``functools.lru_cache`` no expone el mapa (no se puede
vaciar por familia ni sembrar una entrada), y ``django.core.cache`` es caché
de aplicación con backend ``DatabaseCache`` — otro sujeto.

DIVERGENCIA DE ENLACE, declarada: la referencia busca el contenedor en
``model.pool._Registry__caches[nombre]``, porque allá hay un ``Registry`` por
base de datos. Aquí el registry es **el módulo** ``orm/registry.py`` (su
encabezado ya declara por qué: la dimensión por-DB la cubre el router de
``orm/routers.py``), así que el contenedor se pide con ``registry.cache_of``.
La clave, la firma y el comportamiento de acierto/fallo son los de la fuente.

Adaptado de Odoo Community ``odoo/tools/cache.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
# el decorador construye envoltorios con la misma API que la función envuelta
from __future__ import annotations

import functools
import logging
import sys
import time
import typing
import warnings
from collections import defaultdict
from collections.abc import Mapping, Collection
from inspect import signature, Parameter

from django.db import connection
from django.db.models import Model

from orm import registry
from orm.environments import get_context

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from tools.lru import LRU

    C = typing.TypeVar('C', bound=Callable)

unsafe_eval = eval

_logger = logging.getLogger(__name__)


class ormcache_counter:
    """Contadores de estadística de las entradas de caché."""
    __slots__ = ['cache_name', 'err', 'gen_time', 'hit', 'miss', 'tx_err', 'tx_hit', 'tx_miss']

    def __init__(self):
        self.hit: int = 0
        self.miss: int = 0
        self.err: int = 0
        self.gen_time: float = 0.0
        self.cache_name: str = ''
        self.tx_hit: int = 0
        self.tx_miss: int = 0
        self.tx_err: int = 0

    @property
    def ratio(self) -> float:
        return 100.0 * self.hit / (self.hit + self.miss or 1)

    @property
    def tx_ratio(self) -> float:
        return 100.0 * self.tx_hit / (self.tx_hit + self.tx_miss or 1)

    @property
    def tx_calls(self) -> int:
        return self.tx_hit + self.tx_miss


_COUNTERS: defaultdict[Callable, ormcache_counter] = defaultdict(ormcache_counter)
"""Diccionario de contadores; mapea el método a su contador.

La referencia lo indexa por ``(dbname, method)`` porque su ``Registry`` es por
base de datos. Aquí el registry es de proceso, así que la clave es el método.
"""


class ormcache:
    """Decorador de caché LRU para métodos de modelo.

    Los parámetros son cadenas que representan expresiones sobre la firma del
    método decorado, y se usan para computar la clave de caché::

        @ormcache('model_name', 'mode')
        def _compute_domain(self, model_name, mode="read"):
            ...

    Por retrocompatibilidad el decorador admite el parámetro ``skiparg``::

        @ormcache(skiparg=1)
        def _compute_domain(self, model_name, mode="read"):
            ...

    Los métodos que usen este decorador nunca deben devolver un conjunto de
    registros: la conexión subyacente acabará cerrada.
    """
    key: Callable[..., tuple]

    def __init__(self, *args: str, cache: str = 'default', skiparg: int | None = None, **kwargs):
        self.args = args
        self.skiparg = skiparg
        self.cache_name = cache
        if skiparg is not None:
            warnings.warn("Deprecated since 19.0, ormcache(skiparg) will be removed", DeprecationWarning)

    def __call__(self, method: C) -> C:
        assert not hasattr(self, 'method'), "ormcache is already bound to a method"
        self.method = method
        self.determine_key()
        assert self.key is not None, "ormcache.key not initialized"

        @functools.wraps(method)
        def lookup(*args, **kwargs):
            return self.lookup(*args, **kwargs)
        lookup.__cache__ = self  # type: ignore
        return lookup

    def add_value(self, *args, cache_value=None, **kwargs) -> None:
        d: LRU = registry.cache_of(self.cache_name)
        key = self.key(*args, **kwargs)
        d[key] = cache_value

    def determine_key(self) -> None:
        """Determina la función que computa la clave a partir de los argumentos."""
        assert self.method is not None
        if self.skiparg is not None:
            # función retrocompatible que usa self.skiparg
            self.key = lambda *args, **kwargs: (args[0]._name, self.method, *args[self.skiparg:])
            return
        # construye una cadena que representa el código de la función y la evalúa
        parametros = list(signature(self.method).parameters.values())
        args = ', '.join(
            # sin anotaciones: una lambda no las admite
            str(params.replace(annotation=Parameter.empty))
            for params in parametros
        )
        # La fuente escribe ``'self._name'`` literal, porque allá el primer
        # parámetro de un método de modelo se llama siempre ``self``. Aquí hay
        # métodos portados como ``classmethod`` —divergencia de enlace ya
        # declarada en los modelos que la usan—, así que el receptor se toma de
        # la firma en vez de suponerse. Con un método de instancia el resultado
        # es idéntico al de la fuente.
        receptor = parametros[0].name if parametros else 'self'
        values = [f'{receptor}._name', 'method', *self.args]
        code = f"lambda {args}: ({''.join(a for arg in values for a in (arg, ','))})"
        self.key = unsafe_eval(code, {'method': self.method})

    def lookup(self, *args, **kwargs):
        d: LRU = registry.cache_of(self.cache_name)
        key = self.key(*args, **kwargs)
        counter = _COUNTERS[self.method]

        # tx: ¿es la primera llamada de la transacción para esa clave?
        tx_lookups = _tx_lookups()
        tx_key = tuple(map(hash, key))
        tx_first_lookup = tx_key not in tx_lookups
        if tx_first_lookup:
            counter.cache_name = self.cache_name
            tx_lookups.add(tx_key)

        try:
            r = d[key]
            counter.hit += 1
            counter.tx_hit += tx_first_lookup
            return r
        except KeyError:
            counter.miss += 1
            counter.tx_miss += tx_first_lookup
            miss = True
        except TypeError:
            _logger.warning("cache lookup error on %r", key, exc_info=True)
            counter.err += 1
            counter.tx_err += tx_first_lookup
            miss = False

        if miss:
            start = time.monotonic()
            value = self.method(*args, **kwargs)
            counter.gen_time += time.monotonic() - start
            d[key] = value
            return value
        else:
            return self.method(*args, **kwargs)


class ormcache_context(ormcache):
    """Variante de :class:`ormcache` con un parámetro extra ``keys`` que define
    una secuencia de claves de diccionario. Esas claves se buscan en el
    parámetro ``context`` y se combinan con la clave que hace :class:`ormcache`.
    """
    def __init__(self, *args: str, keys, skiparg=None, **kwargs):
        assert skiparg is None, "ormcache_context() no longer supports skiparg"
        warnings.warn(
            "Since 19.0, use ormcache directly, context values are available "
            "as `environments.get_context().get`",
            DeprecationWarning,
        )
        self.keys = keys
        super().__init__(*args, **kwargs)

    def determine_key(self) -> None:
        assert self.method is not None
        sign = signature(self.method)
        cont_expr = "(context or {})" if 'context' in sign.parameters else "_get_context()"
        keys_expr = "tuple(%s.get(k) for k in %r)" % (cont_expr, self.keys)
        self.args += (keys_expr,)
        super().determine_key()


def _tx_lookups() -> set:
    """Claves ya consultadas en la transacción en curso.

    DIVERGENCIA DE ENLACE, declarada: la referencia las guarda en
    ``model.env.cr.cache`` —el cursor de su transacción— porque su ORM lleva
    la transacción como objeto. Aquí la transacción es la de Django y su
    portador equivalente es el estado por conexión, así que las claves cuelgan
    del objeto ``connection``, que Django recrea por transacción/hilo. Sirven
    sólo a los contadores ``tx_*``: no deciden acierto ni fallo.
    """
    lookups = getattr(connection, '_ormcache_lookups', None)
    if lookups is None:
        lookups = set()
        connection._ormcache_lookups = lookups
    return lookups


def _get_context() -> dict:
    """El contexto vigente, para ``ormcache_context`` — el de ``self.env.context``."""
    return get_context()


def log_ormcache_stats() -> None:
    """Registra las estadísticas de uso de ``ormcache`` por método.

    DIVERGENCIA DE MECANISMO, declarada: la referencia la cuelga de los
    manejadores de ``SIGUSR1``/``SIGUSR2`` y recorre ``Registry.registries``
    —un registry por base—. Aquí el registry es de proceso y bajo Gunicorn las
    dos señales las consume el propio servidor (``setup/gunicorn.conf.py``),
    así que la función se invoca directamente y recorre los contenedores del
    módulo. El cuerpo del informe —entradas, aciertos, fallos, tiempo de
    generación y razón de acierto— es el de la fuente.
    """
    log_msgs = ['Caches stats:']
    for cache_name, cache in registry._CACHES.items():
        log_msgs.append(f' * {cache_name}: {len(cache)}/{cache.count}')
    log_msgs.append(
        f"{'Cache Name':>25},{'Hit':>6},{'Miss':>6},{'Err':>6},"
        f"{'Gen Time [s]':>13},{'Hit Ratio':>10},{'TX Hit Ratio':>13},"
        f"{'TX Call':>8},  Method"
    )
    for method, counter in sorted(_COUNTERS.items(), key=lambda kv: kv[0].__qualname__):
        log_msgs.append(
            f'{counter.cache_name:>25},'
            f'{counter.hit:6d},'
            f'{counter.miss:6d},'
            f'{counter.err:6d},'
            f'{counter.gen_time:13.3f},'
            f'{counter.ratio:9.1f}%,'
            f'{counter.tx_ratio:12.1f}%,'
            f'{counter.tx_calls:8d},'
            f'  {method.__qualname__}'
        )
    _logger.info('\n'.join(log_msgs))


def get_cache_key_counter(bound_method: Callable, *args, **kwargs) -> tuple[LRU, tuple, ormcache_counter]:
    """Devuelve la caché, la clave y el contador de la llamada dada."""
    model = bound_method.__self__  # type: ignore
    ormcache_instance: ormcache = bound_method.__cache__  # type: ignore
    cache: LRU = registry.cache_of(ormcache_instance.cache_name)
    key = ormcache_instance.key(model, *args, **kwargs)
    counter = _COUNTERS[ormcache_instance.method]
    return cache, key, counter


def get_cache_size(
        obj,
        *,
        cache_info: str = '',
        seen_ids: set[int] | None = None,
        class_slots: dict[type, Iterable[str]] | None = None,
    ) -> int:
    """Estimador recursivo, no seguro entre hilos, del tamaño de un objeto."""
    if seen_ids is None:
        # las constantes internas cuentan como 0 bytes
        seen_ids = set(map(id, (None, False, True)))
    if class_slots is None:
        class_slots = {}  # {class_id: slots combinados}
    total_size = 0
    objects = [obj]

    while objects:
        cur_obj = objects.pop()
        if id(cur_obj) in seen_ids:
            continue

        if cache_info and isinstance(cur_obj, Model):
            _logger.error('%s is cached by %s', cur_obj, cache_info)
            continue

        seen_ids.add(id(cur_obj))
        total_size += sys.getsizeof(cur_obj)

        if hasattr(cur_obj, '__slots__'):
            cur_obj_cls = type(cur_obj)
            attributes = class_slots.get(id(cur_obj_cls))
            if attributes is None:
                class_slots[id(cur_obj_cls)] = attributes = tuple({
                    f'_{cls.__name__}{attr}' if attr.startswith('__') else attr
                    for cls in cur_obj_cls.mro()
                    for attr in getattr(cls, '__slots__', ())
                })
            objects.extend(getattr(cur_obj, attr, None) for attr in attributes)
        if hasattr(cur_obj, '__dict__'):
            objects.append(object.__dict__)

        if isinstance(cur_obj, Mapping):
            objects.extend(cur_obj.values())
            objects.extend(cur_obj.keys())
        elif isinstance(cur_obj, Collection) and not isinstance(cur_obj, (str, bytes, bytearray)):
            objects.extend(cur_obj)

    return total_size
