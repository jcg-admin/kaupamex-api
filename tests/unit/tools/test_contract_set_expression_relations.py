"""Relaciones de ``tools.set_expression`` medidas contra la fuente ejecutada.

``test_set_expression_against_the_reference.py`` compara lo que cada
expresión **dice de sí misma** —``str``, ``key``, ``matches``…— y deja
sin ejercitar lo que una expresión dice **de otra**. Medido con un
perfilador sobre aquel diferencial: ``Union.__le__``, ``Union.__lt__``,
``Union.__hash__``, ``Inter.__lt__``, ``Inter.__hash__``, ``Leaf.__eq__``,
``Leaf.__lt__`` y ``Leaf.__hash__`` reciben **cero** llamadas. Este archivo
los ejercita.

Las tres capas se comparan par a par, cada una con su propia población:
las uniones de la batería, las intersecciones que esas uniones contienen y las
hojas que esas intersecciones contienen. La fuente se carga por ruta con el
mismo cargador que el diferencial hermano, y la batería es la misma.

*Métrica:* el valor de ``==``, ``!=``, ``<=``, ``<`` y de la igualdad de
``hash`` sobre cada par ordenado de una muestra de cada capa, más el conjunto
de métodos abstractos de ``SetExpression`` y la tupla ``__slots__`` de cada
clase que la declara.
*Ciega a:* el valor numérico de ``hash`` —depende de la semilla del proceso,
así que se compara qué pares colisionan, no el número—, y a toda
divergencia que la fuente comparta con nosotros, porque el oráculo es ella.
"""
import itertools

import pytest

from tests.unit.tools.test_set_expression_against_the_reference import (
    DEFINITIONS, battery, observed, reference_module)
from tools import set_expression as ported

pytestmark = pytest.mark.unit

#: Tamaño de la muestra por capa. Con 160 elementos son 25 440 pares ordenados
#: por capa; la batería entera daría millones sin visitar ramas nuevas.
SAMPLE_SIZE = 160

RELATIONS = (
    ('==', lambda left, right: left == right),
    ('!=', lambda left, right: left != right),
    ('<=', lambda left, right: left <= right),
    ('<', lambda left, right: left < right),
    ('hash==', lambda left, right: hash(left) == hash(right)),
)


def sample(items):
    """Muestra determinista a paso fijo, para cubrir también los compuestos."""
    step = max(1, len(items) // SAMPLE_SIZE)
    return items[::step][:SAMPLE_SIZE]


def unique_by_key(items):
    """Un representante por clave, en el orden de primera aparición."""
    seen = {}
    for item in items:
        seen.setdefault(item.key, item)
    return list(seen.values())


def layers(module, unions):
    """Las tres poblaciones: uniones, sus intersecciones y sus hojas."""
    inters = unique_by_key(
        inter for union in unions
        for inter in getattr(union, '_Union__inters'))
    leaves = unique_by_key(leaf for inter in inters for leaf in inter.leaves)
    return {'Union': unions, 'Inter': inters, 'Leaf': leaves}


@pytest.fixture(scope='module')
def both():
    reference = reference_module()
    if reference is None:
        pytest.skip('la referencia no está montada en esta sesión')
    their = sample(battery(reference.SetDefinitions(dict(DEFINITIONS))))
    ours = sample(battery(ported.SetDefinitions(dict(DEFINITIONS))))
    return reference, layers(reference, their), layers(ported, ours)


@pytest.mark.reference
class TestTheRelationsMatchTheReference:
    """Cada relación entre dos elementos de una capa, contra la fuente."""

    @pytest.mark.parametrize('layer', ['Union', 'Inter', 'Leaf'])
    def test_every_pair_relates_as_in_the_reference(self, both, layer):
        _reference, theirs, ours = both
        their_items, our_items = theirs[layer], ours[layer]
        assert [item.key for item in their_items] == \
            [item.key for item in our_items]
        assert len(our_items) > 10, (
            f'la capa {layer} encogió a {len(our_items)}')

        divergences = []
        comparisons = 0
        pairs = zip(itertools.product(their_items, repeat=2),
                    itertools.product(our_items, repeat=2))
        for (their_left, their_right), (our_left, our_right) in pairs:
            for name, relation in RELATIONS:
                comparisons += 1
                expected = observed(lambda: relation(their_left, their_right))
                actual = observed(lambda: relation(our_left, our_right))
                if expected != actual:
                    divergences.append((name, our_left.key, our_right.key))
        assert not divergences, (
            f'{len(divergences)} de {comparisons} relaciones en {layer} '
            'divergen; '
            f'las tres primeras: {divergences[:3]}')

    def test_a_union_is_not_comparable_with_a_foreign_object(self, both):
        reference, theirs, ours = both
        for their_union, our_union in zip(theirs['Union'], ours['Union']):
            for foreign in (None, 0, 'A', object()):
                assert observed(lambda: their_union == foreign) == \
                    observed(lambda: our_union == foreign)
                assert observed(lambda: their_union <= foreign) == \
                    observed(lambda: our_union <= foreign)
        assert reference is not None

    def test_a_union_hashes_by_its_key(self, both):
        _reference, _theirs, ours = both
        for union in ours['Union']:
            assert hash(union) == hash(union.key)


@pytest.mark.reference
class TestTheDeclarationsMatchTheReference:
    """Lo que la clase declara, no lo que una instancia hace."""

    def test_the_base_declares_the_same_abstract_methods(self, both):
        reference, _theirs, _ours = both
        assert ported.SetExpression.__abstractmethods__ == \
            reference.SetExpression.__abstractmethods__
        with pytest.raises(TypeError):
            ported.SetExpression()

    @pytest.mark.parametrize(
        'name', ['SetDefinitions', 'Inter', 'Leaf', 'UnknownId'])
    def test_the_slots_are_the_reference_slots(self, both, name):
        reference, _theirs, _ours = both
        ours = getattr(ported, name).__slots__
        assert ours == getattr(reference, name).__slots__


class TestTheRelationsLiterally:
    """Tres casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_a_subset_is_strictly_below_its_superset(self):
        definitions = ported.SetDefinitions(dict(DEFINITIONS))
        child, parent = definitions.parse('A1'), definitions.parse('A')
        assert child <= parent
        assert child < parent
        assert not parent <= child

    def test_an_expression_is_not_strictly_below_itself(self):
        definitions = ported.SetDefinitions(dict(DEFINITIONS))
        expression = definitions.parse('A1,!B')
        assert expression <= expression
        assert not expression < expression

    def test_equal_expressions_hash_alike(self):
        definitions = ported.SetDefinitions(dict(DEFINITIONS))
        left = definitions.parse('A1,B')
        right = definitions.parse('B,A1')
        assert left == right
        assert hash(left) == hash(right)
