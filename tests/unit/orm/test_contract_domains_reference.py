"""``orm.domains`` medido contra la fuente ejecutada, sin modelo.

Se carga ``odoo19c: odoo/orm/domains.py`` con el paquete sustituto de
``tests/fixtures/reference_domains.py`` —sólo módulos de la referencia; sus
dos sustituciones están declaradas allí— y se le da al puerto y a la fuente
la misma rejilla de dominios: construcción, ``&``, ``|``, ``~``, igualdad,
hash, iteración, ``repr`` y los predicados de verdad.

El hash recibe una rejilla propia porque es donde el puerto divergía: la
fuente hashea ``value`` y rechaza un valor no hashable (lista, conjunto,
``OrderedSet``) con ``TypeError``; el puerto hasheaba ``str(value)``.

*Métrica:* el valor —o el nombre de la excepción— de cada operación de
las dos rejillas.
*Ciega a:* todo lo que necesita un modelo —``optimize`` con campos,
``validate``, ``_as_predicate``, la traducción a SQL— y a toda divergencia
que la fuente comparta con nosotros.
"""
import pathlib

import pytest

from orm import domains as ported
from tests.fixtures import reference_domains
from tests.fixtures.reference_tree import reference_root
from tools.misc import OrderedSet

pytestmark = pytest.mark.unit


@pytest.fixture(scope='module')
def reference():
    root = pathlib.Path(reference_root())
    if not (root / 'odoo' / 'orm' / 'domains.py').is_file():
        pytest.skip('la referencia no está montada en esta sesión')
    return reference_domains.load_reference_domains(root)


def outcome(call):
    try:
        value = call()
    except Exception as error:
        return ('raises', type(error).__name__)
    return ('value', type(value).__name__, repr(value))


DOMAINS = (
    [], [('a', '=', 1)], ['&', ('a', '=', 1), ('b', '!=', 2)],
    ['|', ('a', '=', 1), '!', ('b', 'in', [1, 2])], [(1, '=', 1)],
    [(0, '=', 1)], ('a', '=', 1), True, False,
    [('a', 'like', 'x'), ('b', 'any', [('c', '=', 3)])],
    ['!', '!', ('a', '=', 1)], [('a', 'bogus', 1)], ['&', ('a', '=', 1)],
    'nonsense', [('a.b.c', 'child_of', 5)], [('a', '=', None)],
    [('a', '<>', 1)],
)
OPERATIONS = {
    'construct': lambda D, d: D(d),
    'list': lambda D, d: list(D(d)),
    'and': lambda D, d: list(D(d) & D('a', '=', 9)),
    'or': lambda D, d: list(D(d) | D('a', '=', 9)),
    'invert': lambda D, d: list(~D(d)),
    'is_true': lambda D, d: D(d).is_true(),
    'is_false': lambda D, d: D(d).is_false(),
    'bool': lambda D, d: bool(D(d)),
    'eq_self': lambda D, d: D(d) == D(d),
    'hash_eq': lambda D, d: hash(D(d)) == hash(D(d)),
    'reversed': lambda D, d: list(reversed(D(d))),
    'add_list': lambda D, d: D(d) + [('z', '=', 1)],
    'conditions': lambda D, d: [list(c) for c in D(d).iter_conditions()],
    'type': lambda D, d: type(D(d)).__name__,
}


def condition_values(module, ordered_set):
    """Un valor de cada forma que ``DomainCondition`` puede llevar."""
    return {
        'int': ('=', 1), 'str': ('=', 'x'), 'none': ('=', None),
        'false': ('=', False), 'list': ('in', [1, 2]),
        'tuple': ('in', (1, 2)), 'set': ('in', {1, 2}),
        'frozenset': ('in', frozenset({1, 2})),
        'ordered_set': ('in', ordered_set([1, 2])),
        'domain': ('any', module.Domain('b', '=', 3)),
        'list_domain': ('any', [('b', '=', 3)]),
    }


def hash_trace(module, ordered_set):
    steps = []
    for label, (operator, value) in condition_values(
            module, ordered_set).items():

        def condition(operator=operator, value=value):
            return module.DomainCondition('a', operator, value)

        steps += [
            (label, 'equal', outcome(lambda: condition() == condition())),
            (label, 'hash_equal',
             outcome(lambda: hash(condition()) == hash(condition()))),
            (label, 'in_set', outcome(lambda: condition() in {condition()})),
            (label, 'nary_hash', outcome(lambda: hash(module.Domain.AND(
                [condition(), module.Domain('c', '=', 1)])) is not None)),
            (label, 'negated_hash',
             outcome(lambda: hash(~condition()) is not None)),
        ]
    steps.append(('distinct', 'equal', outcome(
        lambda: module.DomainCondition('a', '=', 1)
        == module.DomainCondition('a', '=', 2))))
    steps.append(('class', 'equal', outcome(
        lambda: module.DomainCondition('a', '=', 1)
        == module.DomainCondition('a', '=', True))))
    return steps


class TestDomainsBehaveLikeTheReference:

    def test_every_operation_matches_the_reference(self, reference):
        divergences = []
        with reference_domains.runtime():
            for domain in DOMAINS:
                for name, operation in OPERATIONS.items():
                    theirs = outcome(lambda: operation(reference.Domain,
                                                       domain))
                    ours = outcome(lambda: operation(ported.Domain, domain))
                    if theirs != ours:
                        divergences.append((name, domain, theirs, ours))
        assert len(DOMAINS) * len(OPERATIONS) >= 238
        assert not divergences, divergences[:3]

    def test_hash_and_equality_match_the_reference(self, reference):
        with reference_domains.runtime():
            theirs = hash_trace(reference, reference.OrderedSet)
        ours = hash_trace(ported, OrderedSet)
        divergences = [(a[:2], a[2], b[2])
                       for a, b in zip(theirs, ours) if a != b]
        assert len(ours) >= 57
        assert not divergences, divergences[:3]


class TestConditionHashLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    @pytest.mark.parametrize('value', [[1, 2], {1, 2}, OrderedSet([1, 2])],
                             ids=['list', 'set', 'ordered_set'])
    def test_an_unhashable_value_refuses_to_hash(self, value):
        with pytest.raises(TypeError):
            hash(ported.DomainCondition('a', 'in', value))

    def test_equal_conditions_hash_alike(self):
        first = ported.DomainCondition('a', 'in', frozenset({1, 2}))
        second = ported.DomainCondition('a', 'in', frozenset({2, 1}))
        assert first == second
        assert hash(first) == hash(second)
