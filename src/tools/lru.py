"""``tools.lru`` — espejo de ``odoo/tools/lru.py`` (Odoo 19).

Mapa acotado por conteo, con desalojo del menos usado recientemente. Es la
estructura sobre la que descansa cada caché del registry (``ormcache``), y se
porta **verbatim**: el stack no trae un equivalente. ``functools.lru_cache``
decora una función y no expone el mapa —no se puede vaciar por clave ni
inspeccionar—, y ``django.core.cache`` es caché de aplicación (backend
``DatabaseCache`` aquí), no una estructura en memoria del proceso.

Adaptado de Odoo Community ``odoo/tools/lru.py`` (LGPL-3) — atribución y aviso
de licencia preservados (DEC-KX-03).
"""
import threading
import typing
from collections.abc import Iterable, Iterator, MutableMapping

from tools.misc import SENTINEL

__all__ = ['LRU']

K = typing.TypeVar('K')
V = typing.TypeVar('V')


class LRU(MutableMapping[K, V], typing.Generic[K, V]):
    """Mapa acotado por conteo, con desalojo del menos usado recientemente.

    El mapa es seguro entre hilos, y usa internamente un cerrojo para evitar
    problemas de concurrencia. Sin embargo, las operaciones de acceso como
    ``lru[key]`` son rápidas y sin cerrojo.
    """

    __slots__ = ('_count', '_lock', '_ordering', '_values')

    def __init__(self, count: int, pairs: Iterable[tuple[K, V]] = ()):
        assert count > 0, "LRU needs a positive count"
        self._count = count
        self._lock = threading.RLock()
        self._values: dict[K, V] = {}
        #
        # El dict ``self._values`` contiene los ítems; ``self._ordering`` sólo
        # lleva su orden, con los más recientes al final. Por rendimiento, el
        # cerrojo se toma sólo al modificar, mientras que leer es libre.
        #
        # Esa estrategia puede producir inconsistencias entre ``_values`` y
        # ``_ordering``: una clave accedida concurrentemente puede faltar de
        # ``_ordering``, y se añadirá después. De ahí el invariante:
        #
        #     self._values <= self._ordering | "claves en acceso"
        #
        self._ordering: dict[K, None] = {}

        # Inicializar
        for key, value in pairs:
            self[key] = value

    @property
    def count(self) -> int:
        return self._count

    @count.setter
    def count(self, count: int):
        assert count > 0, "LRU needs a positive count"
        with self._lock:
            self._count = count
            while len(self) > count:
                self.popitem()

    def __contains__(self, key: object) -> bool:
        return key in self._values

    def __getitem__(self, key: K) -> V:
        val = self._values[key]
        # mueve la clave a la última posición de ``self._ordering``
        self._ordering[key] = self._ordering.pop(key, None)
        return val

    def __setitem__(self, key: K, val: V):
        values = self._values
        ordering = self._ordering
        with self._lock:
            values[key] = val
            ordering[key] = ordering.pop(key, None)
            while True:
                # si sobran claves en ordering, filtrarlas
                if len(ordering) > len(values):
                    # (copia para evitar cambios concurrentes en ordering)
                    for k in ordering.copy():
                        if k not in values:
                            ordering.pop(k, None)
                # comprobar si hay demasiadas claves
                if len(values) <= self._count:
                    break
                # si las hay, desalojar la menos usada recientemente
                try:
                    # con default por si hay accesos concurrentes
                    key = next(iter(ordering), key)
                except RuntimeError:
                    # ordering cambió durante la iteración; reintentar
                    continue
                values.pop(key, None)
                ordering.pop(key, None)

    def __delitem__(self, key: K):
        self.pop(key)

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[K]:
        return iter(self.snapshot)

    @property
    def snapshot(self) -> dict[K, V]:
        """Copia del LRU, ordenada del menos usado recientemente al más."""
        with self._lock:
            values = self._values
            # construir el resultado en el orden esperado (copia de
            # ``self._ordering`` para evitar cambios concurrentes)
            result = {
                key: val
                for key in self._ordering.copy()
                if (val := values.get(key, SENTINEL)) is not SENTINEL
            }
            if len(result) < len(values):
                # había claves en values ausentes de ``self._ordering``
                result.update(values)
        return result

    def pop(self, key: K, /, default=SENTINEL) -> V:
        with self._lock:
            self._ordering.pop(key, None)
            if default is SENTINEL:
                return self._values.pop(key)
            return self._values.pop(key, default)

    def clear(self):
        with self._lock:
            self._ordering.clear()
            self._values.clear()
