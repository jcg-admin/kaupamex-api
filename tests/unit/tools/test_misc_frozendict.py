"""``tools.misc.frozendict`` y ``freehash`` — el mapa inmutable y hashable.

Los pide ``EMPTY_DICT = frozendict()`` de ``odoo19c:
odoo/orm/environments.py:636``, que ``Cache.get_records`` usa como centinela
del cubo ausente. Ninguno de los dos existía en este árbol antes de este pase
(medido: 0 hits de ``class frozendict`` y ``def freehash`` en ``src/``).

**No sustituye a** :class:`~tools.misc.ReadonlyDict`, y el docstring de aquél
ya declara por qué conviven: ``ReadonlyDict`` hereda de ``Mapping`` y es
estricto —``dict.update`` no lo atraviesa—; ``frozendict`` hereda de ``dict``,
así que ``json.dumps`` lo conoce de serie y ``dict.update`` **sí** lo
atraviesa. Los dos casos que fijan esa frontera están abajo: si alguien
«mejora» ``frozendict`` haciéndolo estricto, dejará de ser el de la fuente.
"""
import json

import pytest

from tools.misc import ReadonlyDict, freehash, frozendict


class TestTheFrozenMappingRefusesToBeModified:
    """Los siete métodos que la fuente niega (``odoo19c: misc.py:963-982``)."""

    @pytest.mark.parametrize('operation', [
        lambda d: d.__setitem__('a', 2),
        lambda d: d.__delitem__('a'),
        lambda d: d.clear(),
        lambda d: d.pop('a'),
        lambda d: d.popitem(),
        lambda d: d.setdefault('b', 1),
        lambda d: d.update({'b': 1}),
    ])
    def test_the_seven_mutators_raise(self, operation):
        with pytest.raises(NotImplementedError):
            operation(frozendict({'a': 1}))

    def test_reading_still_works(self):
        data = frozendict({'a': 1, 'b': 2})
        assert data['a'] == 1
        assert sorted(data) == ['a', 'b']
        assert len(data) == 2


class TestTheFrozenMappingIsStillADict:
    """Hereda de ``dict``, y de ahí salen sus dos propiedades útiles."""

    def test_json_serializes_it_without_a_hook(self):
        """Lo que ``ReadonlyDict`` no puede — su docstring lo declara."""
        assert json.loads(json.dumps(frozendict({'a': 1}))) == {'a': 1}
        with pytest.raises(TypeError):
            json.dumps(ReadonlyDict({'a': 1}))

    def test_the_unbound_dict_update_does_go_through(self):
        """El precio de heredar de ``dict``, y es el de la fuente.

        No es un defecto que corregir: es la diferencia por la que el árbol
        tiene las dos clases. ``ReadonlyDict`` es el estricto.
        """
        data = frozendict({'a': 1})
        dict.update(data, {'b': 2})
        assert data['b'] == 2

    def test_it_is_hashable_unlike_a_plain_dict(self):
        assert hash(frozendict({'a': 1})) == hash(frozendict({'a': 1}))
        with pytest.raises(TypeError):
            hash({'a': 1})

    def test_the_empty_one_is_falsy(self):
        """Lo que hace de ``EMPTY_DICT`` un centinela utilizable."""
        assert not frozendict()


class TestFreehashFallsBackInsteadOfRaising:
    """≙ ``freehash`` (``odoo19c: misc.py:940-949``) — nunca levanta."""

    def test_a_hashable_value_hashes_as_itself(self):
        assert freehash('x') == hash('x')

    def test_a_mapping_hashes_through_the_frozen_one(self):
        assert freehash({'a': 1}) == hash(frozendict({'a': 1}))

    def test_an_iterable_hashes_as_a_frozenset_of_its_items(self):
        assert freehash([1, 2]) == hash(frozenset({freehash(1), freehash(2)}))

    def test_a_nested_unhashable_still_hashes(self):
        """El caso que motiva la recursión: lista de dicts."""
        assert isinstance(freehash([{'a': 1}, {'b': 2}]), int)

    def test_an_object_that_is_neither_falls_back_to_its_identity(self):
        class Neither:
            __hash__ = None

        value = Neither()
        assert freehash(value) == id(value)


class TestTheFrozenMappingHashesWhatADictCannot:
    """El motivo de que ``__hash__`` use ``freehash`` y no ``hash``."""

    def test_a_value_that_is_a_list_does_not_break_the_hash(self):
        assert isinstance(hash(frozendict({'a': [1, 2]})), int)

    def test_two_equal_ones_with_unhashable_values_agree(self):
        assert hash(frozendict({'a': [1]})) == hash(frozendict({'a': [1]}))
