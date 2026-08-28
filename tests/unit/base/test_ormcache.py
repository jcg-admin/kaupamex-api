"""Gate del caché de métodos de modelo = ``odoo/tools/cache.py`` (Odoo 19).

Escrito antes que la implementación (TDD). Cubre las tres piezas que la
referencia declara: el mapa acotado ``LRU``, el decorador ``ormcache`` y el
vaciado por nombre de caché que ``Registry.clear_cache`` expone.
"""
import pytest

from orm import registry
from tools.cache import _COUNTERS, ormcache, get_cache_key_counter
from tools.lru import LRU


class TestLru:
    """``LRU`` â€” mapa acotado por conteo, el que sostiene cada caché."""

    def test_keeps_the_declared_count_at_most(self):
        lru = LRU(2)
        lru['a'], lru['b'], lru['c'] = 1, 2, 3
        assert len(lru) == 2

    def test_evicts_the_least_recently_used(self):
        lru = LRU(2)
        lru['a'], lru['b'] = 1, 2
        lru['a']                      # 'a' pasa a ser el más reciente
        lru['c'] = 3
        assert 'a' in lru and 'c' in lru and 'b' not in lru

    def test_snapshot_comes_out_least_recently_used_first(self):
        lru = LRU(3)
        lru['a'], lru['b'], lru['c'] = 1, 2, 3
        lru['a']
        assert list(lru.snapshot) == ['b', 'c', 'a']

    def test_clear_empties_it(self):
        lru = LRU(2)
        lru['a'] = 1
        lru.clear()
        assert len(lru) == 0

    def test_refuses_a_non_positive_count(self):
        with pytest.raises(AssertionError):
            LRU(0)


class _Cached:
    """Modelo de juguete: lo que ``ormcache`` necesita es ``_name``."""

    _name = 'test.ormcache'

    def __init__(self):
        self.calls = 0

    @ormcache('argument')
    def compute(self, argument):
        self.calls += 1
        return argument * 2

    @ormcache('argument', cache='stable')
    def stable_compute(self, argument):
        self.calls += 1
        return argument * 3


class TestOrmcache:
    """``ormcache`` â€” el decorador de método de modelo."""

    def setup_method(self):
        registry.clear_all_caches()

    def test_the_second_call_does_not_reach_the_method(self):
        subject = _Cached()
        assert subject.compute(21) == 42
        assert subject.compute(21) == 42
        assert subject.calls == 1

    def test_a_different_argument_is_a_different_entry(self):
        subject = _Cached()
        subject.compute(1)
        subject.compute(2)
        assert subject.calls == 2

    def test_clear_cache_by_name_only_empties_its_containers(self):
        """``templates`` no arrastra a ``default`` ni a ``stable``.

        El mapa de dependencias de la referencia (``_CACHES_BY_KEY``) declara
        ``templates -> (templates, templates.cached_values)``: ninguno de los
        dos contenedores es el de estos dos métodos, así que las dos entradas
        sobreviven y el método no se vuelve a llamar.
        """
        subject = _Cached()
        subject.compute(1)
        subject.stable_compute(1)
        registry.clear_cache('templates')
        subject.compute(1)
        subject.stable_compute(1)
        assert subject.calls == 2

    def test_stable_drags_default_as_the_reference_declares(self):
        """``stable -> (stable, default, ...)``: vaciar ``stable`` vacía ``default``.

        No es un efecto colateral: es la dependencia que ``_CACHES_BY_KEY``
        declara verbatim, y el gate la fija para que un cambio del mapa no pase
        inadvertido.
        """
        subject = _Cached()
        subject.compute(1)
        subject.stable_compute(1)
        registry.clear_cache('stable')
        subject.compute(1)
        subject.stable_compute(1)
        assert subject.calls == 4

    def test_clear_all_caches_empties_every_one(self):
        subject = _Cached()
        subject.compute(1)
        subject.stable_compute(1)
        registry.clear_all_caches()
        subject.compute(1)
        subject.stable_compute(1)
        assert subject.calls == 4

    def test_the_key_carries_the_model_name_and_the_method(self):
        subject = _Cached()
        cache, key, counter = get_cache_key_counter(subject.compute, 7)
        assert key[0] == 'test.ormcache'
        assert key[2] == 7

    def test_the_counter_separates_hit_from_miss(self):
        """El contador vive en el módulo y acumula entre llamadas, como la
        fuente: por eso se mide el delta y no el valor absoluto.
        """
        subject = _Cached()
        _, _, counter = get_cache_key_counter(subject.compute, 5)
        antes = (counter.miss, counter.hit)
        subject.compute(5)
        subject.compute(5)
        assert (counter.miss - antes[0], counter.hit - antes[1]) == (1, 1)

    def test_clear_cache_refuses_a_dotted_name(self):
        with pytest.raises(AssertionError):
            registry.clear_cache('templates.cached_values')

    def test_add_value_seeds_an_entry_without_calling_the_method(self):
        subject = _Cached()
        _Cached.compute.__cache__.add_value(subject, 9, cache_value=999)
        assert subject.compute(9) == 999
        assert subject.calls == 0
