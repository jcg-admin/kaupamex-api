"""Las fusiones n-arias — la tercera familia, y la mitad vacia del registro.

``nary_optimization`` y ``nary_condition_optimization`` existen desde
``api@d7f4b8e4`` y ``_MERGE_OPTIMIZATIONS`` estaba **vacia**: el adaptador
recorria los hijos ordenados, formaba bloques por campo y no habia a quien
entregarselos. Es la misma mitad muerta que era el despacho por tipo de campo
antes de :ref:`h-api-961`, en el otro eje del registro.

La familia fusiona condiciones **contiguas del mismo campo** en una sola:

    a in {1} or a in {2}        <=>  a in {1, 2}
    a in {1, 2} and a not in {2, 5}  =>  a in {1}

El orden lo garantiza ``_optimize_nary_sort_key``, que corre antes de las
fusiones — por eso la familia puede mirar solo bloques contiguos.
"""
import pytest

from addons.base.models.ir_rule import IrRule
from orm.domains import (
    Domain,
    DomainAnd,
    DomainCondition,
    DomainOr,
    _MERGE_OPTIMIZATIONS,
    intersection,
    union,
)
from tools.misc import OrderedSet, partition


class TestTheMergeHalfOfTheRegistryIsPopulated:
    """La mitad n-aria tiene ahora miembros; estaba vacia."""

    def test_there_are_registered_merges(self):
        assert _MERGE_OPTIMIZATIONS, _MERGE_OPTIMIZATIONS


class TestPartition:
    """``partition`` — el ayudante de ``tools/misc`` que la familia consume."""

    def test_it_splits_by_the_predicate(self):
        yes, nos = partition(lambda x: x % 2 == 0, [1, 2, 3, 4])
        assert yes == [2, 4]
        assert nos == [1, 3]

    def test_it_preserves_order_within_each_side(self):
        yes, nos = partition(lambda x: x > 0, [3, -1, 5, -2, 7])
        assert yes == [3, 5, 7]
        assert nos == [-1, -2]

    def test_an_empty_input_gives_two_empty_lists(self):
        assert partition(bool, []) == ([], [])


class TestSetAlgebra:
    """``intersection`` y ``union`` sobre ``OrderedSet``."""

    def test_intersection_of_two(self):
        result = intersection([OrderedSet([1, 2, 3]), OrderedSet([2, 3, 4])])
        assert set(result) == {2, 3}

    def test_union_of_two(self):
        result = union([OrderedSet([1, 2]), OrderedSet([2, 3])])
        assert set(result) == {1, 2, 3}

    def test_union_preserves_the_insertion_order(self):
        """Es lo que distingue un ``OrderedSet`` de un ``set``, y por eso la
        fuente lo usa: el orden de la coleccion llega al SQL emitido."""
        assert list(union([OrderedSet([3, 1]), OrderedSet([2, 1])])) == [3, 1, 2]

    def test_union_of_none_is_empty(self):
        assert list(union([])) == []


class TestMergingTheSameFieldUnderOr:
    """``a in {1} or a in {2}`` es ``a in {1, 2}``."""

    def test_two_in_conditions_become_one(self):
        domain = Domain.OR([
            Domain('name', 'in', ['a']),
            Domain('name', 'in', ['b']),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainCondition), domain
        assert domain.operator == 'in'
        assert set(domain.value) == {'a', 'b'}

    def test_three_in_conditions_become_one(self):
        domain = Domain.OR([
            Domain('name', 'in', ['a']),
            Domain('name', 'in', ['b']),
            Domain('name', 'in', ['c']),
        ]).optimize(IrRule)
        assert set(domain.value) == {'a', 'b', 'c'}

    def test_a_different_field_is_not_merged(self):
        """El control del alcance: la fusion es POR CAMPO, no global."""
        domain = Domain.OR([
            Domain('name', 'in', ['a']),
            Domain('model_name', 'in', ['b']),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainOr), domain
        assert len(domain.children) == 2


class TestMergingTheSameFieldUnderAnd:
    """``a in {1, 2} and a not in {2, 5}`` es ``a in {1}``."""

    def test_in_minus_not_in(self):
        domain = Domain.AND([
            Domain('name', 'in', ['a', 'b']),
            Domain('name', 'not in', ['b', 'z']),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainCondition), domain
        assert domain.operator == 'in'
        assert set(domain.value) == {'a'}

    def test_two_not_in_conditions_become_their_union(self):
        domain = Domain.AND([
            Domain('name', 'not in', ['a']),
            Domain('name', 'not in', ['b']),
        ]).optimize(IrRule)
        assert domain.operator == 'not in'
        assert set(domain.value) == {'a', 'b'}

    def test_two_in_conditions_become_their_intersection(self):
        domain = Domain.AND([
            Domain('name', 'in', ['a', 'b']),
            Domain('name', 'in', ['b', 'c']),
        ]).optimize(IrRule)
        assert domain.operator == 'in'
        assert set(domain.value) == {'b'}

    def test_a_disjoint_intersection_is_the_empty_set(self):
        """``a in {1} and a in {2}`` no tiene solucion.

        La fusion produce el conjunto vacio, y ``_optimize_in_set`` lo colapsa
        a FALSO en la siguiente vuelta del punto fijo. Las dos piezas juntas,
        que es lo que la fuente hace.
        """
        domain = Domain.AND([
            Domain('name', 'in', ['a']),
            Domain('name', 'in', ['b']),
        ]).optimize(IrRule)
        assert domain == Domain.FALSE


class TestTheDualityBetweenAndAndOr:
    """La invariante que ``nary_optimization`` declara verbatim.

    *"you always need to optimize both AND and OR domains"* — la fuente lo
    razona: si se puede optimizar ``a & b`` se puede optimizar ``a | b``,
    porque es optimizar ``~(~a & ~b)``. Cada fusion se escribe en espejo.
    """

    def test_or_of_not_in_is_the_intersection(self):
        """El espejo de ``and`` de ``in``."""
        domain = Domain.OR([
            Domain('name', 'not in', ['a', 'b']),
            Domain('name', 'not in', ['b', 'c']),
        ]).optimize(IrRule)
        assert domain.operator == 'not in'
        assert set(domain.value) == {'b'}


class TestTheSameConditionTwice:
    """``_optimize_same_conditions`` — la fusion mas barata de todas."""

    def test_a_repeated_condition_collapses(self):
        domain = Domain.AND([
            Domain('model_name', '=', 'res.partner'),
            Domain('model_name', '=', 'res.partner'),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainCondition), domain

    def test_a_repeated_condition_under_or_collapses(self):
        domain = Domain.OR([
            Domain('model_name', '=', 'res.partner'),
            Domain('model_name', '=', 'res.partner'),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainCondition), domain

    def test_two_different_conditions_do_not_collapse(self):
        """El control: la fusion mira igualdad, no solo el campo."""
        domain = Domain.AND([
            Domain('model_name', '=', 'res.partner'),
            Domain('name', '=', 'x'),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainAnd), domain
        assert len(domain.children) == 2


class TestX2manyKeepsItsOwnSemantics:
    """Un x2many NO se fusiona como un escalar, y la fuente lo separa.

    ``a in {1} and a in {2}`` sobre un many2many puede tener solucion —un
    registro con las dos lineas— mientras que sobre un escalar no. Por eso
    ``_optimize_merge_set_conditions_mono_value`` deja fuera a x2many y hay
    dos optimizaciones aparte que solo fusionan en el sentido seguro.
    """

    def test_an_and_of_in_over_x2many_is_not_merged(self):
        domain = Domain.AND([
            Domain('groups', 'in', [1]),
            Domain('groups', 'in', [2]),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainAnd), domain
        assert len(domain.children) == 2

    def test_an_or_of_in_over_x2many_is_merged(self):
        """El sentido seguro si fusiona: la union es equivalente."""
        domain = Domain.OR([
            Domain('groups', 'in', [1]),
            Domain('groups', 'in', [2]),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainCondition), domain
        assert set(domain.value) == {1, 2}

    def test_an_or_of_not_in_over_x2many_is_not_merged(self):
        domain = Domain.OR([
            Domain('groups', 'not in', [1]),
            Domain('groups', 'not in', [2]),
        ]).optimize(IrRule)
        assert isinstance(domain, DomainOr), domain
        assert len(domain.children) == 2

    def test_the_scalar_field_is_merged_in_both_directions(self):
        """El contraste que hace verificable la distincion.

        Sin este caso, los tres anteriores no distinguirian *"x2many tiene
        semantica propia"* de *"la fusion no funciona".*
        """
        for combiner in (Domain.AND, Domain.OR):
            domain = combiner([
                Domain('name', 'in', ['a']),
                Domain('name', 'in', ['a']),
            ]).optimize(IrRule)
            assert isinstance(domain, DomainCondition), (combiner, domain)
