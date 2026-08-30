"""El registro de optimizadores de dominio — lo que ``_optimize_step`` esperaba.

Hasta ``api@e85916e1`` los dos ``_optimize_step`` que importan declaraban su
hueco en el docstring y devolvian el dominio sin tocar:

- ``DomainNary._optimize_step`` — *"la fuente ademas ordena los hijos y corre
  ``_MERGE_OPTIMIZATIONS``"*;
- ``DomainCondition._optimize_step`` — *"la fuente despacha aqui los 39
  optimizadores registrados por operador y por tipo de campo"*.

Los dos apuntaban a una tarea **#373 que no existe** en el tablero. Un hueco
declarado con un sucesor inexistente es deuda sin dueño, que es lo que
``hallazgo-abierto-genera-sucesor`` prohibe.

Esta suite mide el **mecanismo**, no los optimizadores concretos: los cuatro
registradores, la llave de orden y las dos rutas de despacho. Los ~33
optimizadores que se registran con el son la tanda siguiente.
"""
import pytest

from orm.domains import (
    _MERGE_OPTIMIZATIONS,
    _OPTIMIZATIONS_FOR,
    CONDITION_OPERATORS,
    Domain,
    DomainAnd,
    DomainCondition,
    DomainOr,
    OptimizationLevel,
    _optimize_nary_sort_key,
    field_type_optimization,
    nary_condition_optimization,
    nary_optimization,
    operator_optimization,
)


@pytest.fixture(autouse=True)
def isolated_registry():
    """Los registros son estado de modulo: se restauran tras cada caso.

    Sin esto, un optimizador de prueba sobreviviria al caso que lo registro y
    contaminaria los demas — incluida la suite de dominios que ya existe.
    """
    saved_for = {level: {op: list(fns) for op, fns in mapping.items()}
                 for level, mapping in _OPTIMIZATIONS_FOR.items()}
    saved_merge = list(_MERGE_OPTIMIZATIONS)
    saved_operators = set(CONDITION_OPERATORS)
    yield
    for level, mapping in _OPTIMIZATIONS_FOR.items():
        mapping.clear()
        mapping.update(saved_for[level])
    _MERGE_OPTIMIZATIONS[:] = saved_merge
    CONDITION_OPERATORS.clear()
    CONDITION_OPERATORS.update(saved_operators)


class TestRegisteringByOperator:
    """``operator_optimization`` — el registro por operador."""

    def test_it_lands_in_the_mapping_of_its_level(self):
        @operator_optimization(['zz_test'])
        def optimizer(condition, model):
            return condition

        assert optimizer in _OPTIMIZATIONS_FOR[OptimizationLevel.BASIC]['zz_test']

    def test_it_returns_the_function_unchanged(self):
        def optimizer(condition, model):
            return condition

        assert operator_optimization(['zz_test'])(optimizer) is optimizer

    def test_it_declares_the_operator_as_constructible(self):
        assert 'zz_test' not in CONDITION_OPERATORS

        @operator_optimization(['zz_test'])
        def optimizer(condition, model):
            return condition

        assert 'zz_test' in CONDITION_OPERATORS

    def test_one_optimizer_can_serve_several_operators(self):
        @operator_optimization(['zz_a', 'zz_b'])
        def optimizer(condition, model):
            return condition

        basic = _OPTIMIZATIONS_FOR[OptimizationLevel.BASIC]
        assert optimizer in basic['zz_a']
        assert optimizer in basic['zz_b']

    def test_the_level_is_honoured(self):
        @operator_optimization(['zz_test'], OptimizationLevel.FULL)
        def optimizer(condition, model):
            return condition

        assert optimizer in _OPTIMIZATIONS_FOR[OptimizationLevel.FULL]['zz_test']
        assert optimizer not in _OPTIMIZATIONS_FOR[OptimizationLevel.BASIC]['zz_test']

    def test_registering_without_operators_is_refused(self):
        with pytest.raises(AssertionError):
            operator_optimization([])

    def test_the_none_level_has_no_mapping(self):
        assert OptimizationLevel.NONE not in _OPTIMIZATIONS_FOR


class TestRegisteringByFieldType:
    """``field_type_optimization`` — el registro por tipo de campo."""

    def test_it_lands_under_the_field_type(self):
        @field_type_optimization(['zz_kind'])
        def optimizer(condition, model):
            return condition

        assert optimizer in _OPTIMIZATIONS_FOR[OptimizationLevel.BASIC]['zz_kind']

    def test_it_does_not_declare_a_new_operator(self):
        @field_type_optimization(['zz_kind'])
        def optimizer(condition, model):
            return condition

        assert 'zz_kind' not in CONDITION_OPERATORS


class TestTheSortKey:
    """``_optimize_nary_sort_key`` — campo, luego familia de operador."""

    def test_a_condition_sorts_by_its_field_first(self):
        key = _optimize_nary_sort_key(DomainCondition('name', '=', 'a'))
        assert key[0] == 'name'

    def test_in_and_not_in_share_their_family(self):
        a = _optimize_nary_sort_key(DomainCondition('name', 'in', ['a']))
        b = _optimize_nary_sort_key(DomainCondition('name', 'not in', ['a']))
        assert a[1] == b[1] == '0in'

    def test_every_like_shares_the_like_family(self):
        for operator in ('like', 'not like', 'ilike', '=like'):
            key = _optimize_nary_sort_key(DomainCondition('name', operator, 'a'))
            assert key[1] == 'like', operator

    def test_the_two_any_families_are_distinct(self):
        assert _optimize_nary_sort_key(
            DomainCondition('a', 'any', Domain.TRUE))[1] == '1any'
        assert _optimize_nary_sort_key(
            DomainCondition('a', 'any!', Domain.TRUE))[1] == '2any'

    def test_a_non_condition_sorts_at_the_end(self):
        """La fuente lo dice verbatim: *"in python; '~' > any letter"*."""
        key = _optimize_nary_sort_key(Domain.TRUE)
        assert key[0] == '~'

    def test_two_conditions_on_the_same_field_land_together(self):
        keys = sorted(_optimize_nary_sort_key(d) for d in [
            DomainCondition('zeta', '=', 1),
            DomainCondition('alfa', '=', 1),
            DomainCondition('zeta', '>', 1),
        ])
        assert [k[0] for k in keys] == ['alfa', 'zeta', 'zeta']


class TestTheNaryMerge:
    """``nary_optimization`` — la capa que fusiona hijos de un n-ario."""

    def test_it_lands_in_the_merge_list(self):
        @nary_optimization
        def optimizer(cls, domains, model):
            return domains

        assert optimizer in _MERGE_OPTIMIZATIONS

    def test_it_returns_the_function_unchanged(self):
        def optimizer(cls, domains, model):
            return domains

        assert nary_optimization(optimizer) is optimizer

    def test_the_nary_step_runs_it(self):
        seen = []

        @nary_optimization
        def optimizer(cls, domains, model):
            seen.append(cls)
            return domains

        DomainAnd([DomainCondition('a', '=', 1),
                   DomainCondition('b', '=', 2)]).optimize()
        assert DomainAnd in seen

    def test_the_nary_step_applies_what_the_merge_returns(self):
        @nary_optimization
        def collapse(cls, domains, model):
            return [DomainCondition('merged', '=', 1)]

        result = DomainAnd([DomainCondition('a', '=', 1),
                            DomainCondition('b', '=', 2)]).optimize()
        assert list(result.iter_conditions())[0].field_expr == 'merged'

    def test_the_children_reach_the_merge_already_sorted(self):
        seen = []

        @nary_optimization
        def optimizer(cls, domains, model):
            seen.append([d.field_expr for d in domains])
            return domains

        DomainAnd([DomainCondition('zeta', '=', 1),
                   DomainCondition('alfa', '=', 2)]).optimize()
        assert seen[0] == ['alfa', 'zeta']

    def test_an_or_domain_runs_the_merge_too(self):
        """La fuente lo exige verbatim: *"you always need to optimize both AND
        and OR domains"* — ``a | b`` es ``~(~a & ~b)``."""
        seen = []

        @nary_optimization
        def optimizer(cls, domains, model):
            seen.append(cls)
            return domains

        DomainOr([DomainCondition('a', '=', 1),
                  DomainCondition('b', '=', 2)]).optimize()
        assert DomainOr in seen


class TestTheConditionBlockAdapter:
    """``nary_condition_optimization`` — agrupa condiciones del mismo campo."""

    def test_it_receives_only_the_matching_block(self):
        seen = []

        @nary_condition_optimization(['in'])
        def optimizer(cls, conditions, model):
            seen.append([c.field_expr for c in conditions])
            return conditions

        DomainAnd([DomainCondition('a', 'in', [1]),
                   DomainCondition('a', 'in', [2]),
                   DomainCondition('b', '>', 3)]).optimize()
        # ``optimize`` repite hasta punto fijo, asi que la fusion puede correr
        # mas de una vez; lo que se asierta es QUE bloque recibe, no cuantas.
        assert set(map(tuple, seen)) == {('a', 'a')}

    def test_a_lone_condition_is_not_a_block(self):
        seen = []

        @nary_condition_optimization(['in'])
        def optimizer(cls, conditions, model):
            seen.append(conditions)
            return conditions

        DomainAnd([DomainCondition('a', 'in', [1]),
                   DomainCondition('b', 'in', [2])]).optimize()
        assert seen == []

    def test_what_it_returns_replaces_the_block(self):
        @nary_condition_optimization(['in'])
        def optimizer(cls, conditions, model):
            return [DomainCondition('a', 'in', [9])]

        result = DomainAnd([DomainCondition('a', 'in', [1]),
                            DomainCondition('a', 'in', [2])]).optimize()
        conditions = list(result.iter_conditions())
        assert len(conditions) == 1
        assert list(conditions[0].value) == [9]

    def test_the_domains_outside_the_block_survive(self):
        @nary_condition_optimization(['in'])
        def optimizer(cls, conditions, model):
            return [DomainCondition('a', 'in', [9])]

        result = DomainAnd([DomainCondition('a', 'in', [1]),
                            DomainCondition('a', 'in', [2]),
                            DomainCondition('z', '>', 3)]).optimize()
        assert {c.field_expr for c in result.iter_conditions()} == {'a', 'z'}

    def test_an_operator_outside_the_set_is_not_grouped(self):
        seen = []

        @nary_condition_optimization(['in'])
        def optimizer(cls, conditions, model):
            seen.append(conditions)
            return conditions

        DomainAnd([DomainCondition('a', '>', 1),
                   DomainCondition('a', '>', 2)]).optimize()
        assert seen == []


class TestTheConditionDispatch:
    """``DomainCondition._optimize_step`` — despacha por operador."""

    def test_a_registered_optimizer_runs(self):
        seen = []

        @operator_optimization(['>'])
        def optimizer(condition, model):
            seen.append(condition.field_expr)
            return condition

        DomainCondition('a', '>', 1).optimize()
        assert seen == ['a']

    def test_what_it_returns_replaces_the_condition(self):
        @operator_optimization(['>'])
        def optimizer(condition, model):
            return DomainCondition('replaced', '=', 1)

        result = DomainCondition('a', '>', 1).optimize()
        assert list(result.iter_conditions())[0].field_expr == 'replaced'

    def test_an_optimizer_of_another_operator_does_not_run(self):
        seen = []

        @operator_optimization(['<'])
        def optimizer(condition, model):
            seen.append(condition)
            return condition

        DomainCondition('a', '>', 1).optimize()
        assert seen == []

    def test_the_first_that_changes_the_domain_wins(self):
        """Control discriminante: la fuente corta en el primero que cambia.

        Si el despacho corriera todos, el segundo veria una condicion que el
        primero ya sustituyo — y el resultado dependeria del orden de registro
        en vez del contrato. Este caso cae si alguien quita el corte.
        """
        seen = []

        @operator_optimization(['>'])
        def first(condition, model):
            seen.append('first')
            return DomainCondition('replaced', '=', 1)

        @operator_optimization(['>'])
        def second(condition, model):
            seen.append('second')
            return condition

        DomainCondition('a', '>', 1).optimize()
        assert seen == ['first']

    def test_an_optimizer_that_changes_nothing_lets_the_next_run(self):
        seen = []

        @operator_optimization(['>'])
        def first(condition, model):
            seen.append('first')
            return condition

        @operator_optimization(['>'])
        def second(condition, model):
            seen.append('second')
            return condition

        DomainCondition('a', '>', 1).optimize()
        assert seen == ['first', 'second']

    def test_a_full_level_optimizer_does_not_run_at_basic(self):
        seen = []

        @operator_optimization(['>'], OptimizationLevel.FULL)
        def optimizer(condition, model):
            seen.append(condition)
            return condition

        DomainCondition('a', '>', 1).optimize()
        assert seen == []
