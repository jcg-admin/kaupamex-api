"""Los optimizadores por TIPO de campo — la segunda familia de las cuatro.

La primera familia (``api@04ac6b64``) normaliza el OPERADOR. Esta normaliza el
VALOR contra el tipo del campo, y hasta ``api@85168364`` no podia despachar:
``field.type`` valia ``''`` en toda familia salvo las dos temporales, asi que
la busqueda del registro no casaba con ninguna clave registrada
(:ref:`h-api-961`).

Se portan tres, mas el ``_optimize_like_str`` de la familia de operador, que
consume ``field.relational`` — el otro atributo que aquel hallazgo cablea.

Los casos usan ``IrRule`` porque tiene las tres formas que la familia
necesita sobre un modelo real: ``active`` es booleano, ``name`` es texto y
``groups`` es relacional. Un campo falso probaria el despacho contra un objeto
que yo mismo declaro; el modelo real lo prueba contra lo que el ORM publica.
"""
import pytest

from addons.base.models.ir_rule import IrRule
from orm.domains import (
    Domain,
    DomainCondition,
    OptimizationLevel,
    _OPTIMIZATIONS_FOR,
)


def _sole(domain):
    """La unica condicion de un dominio de una sola condicion."""
    assert isinstance(domain, DomainCondition), domain
    return domain


class TestTheBooleanFamilyIsRegistered:
    """El despacho por tipo tiene ahora a quien encontrar bajo ``boolean``."""

    def test_boolean_has_optimizers_at_the_basic_level(self):
        assert _OPTIMIZATIONS_FOR[OptimizationLevel.BASIC].get('boolean')

    def test_boolean_has_an_optimizer_at_the_full_level(self):
        assert _OPTIMIZATIONS_FOR[OptimizationLevel.FULL].get('boolean')

    def test_the_model_field_publishes_the_key_the_registry_looks_up(self):
        """El puente: la clave que el registro busca es la que el campo da."""
        assert IrRule._meta.get_field('active').type == 'boolean'


class TestBooleanValuesAreParsed:
    """``b in boolean_values`` — el valor se normaliza a booleanos."""

    def test_a_string_becomes_a_boolean(self):
        result = _sole(Domain('active', 'in', ['True']).optimize(IrRule))
        assert set(result.value) == {True}

    def test_the_false_string_flips_the_operator(self):
        result = _sole(Domain('active', 'in', ['False']).optimize(IrRule))
        assert result.operator == 'not in'
        assert list(result.value) == [True]

    def test_a_single_false_flips_the_operator(self):
        result = _sole(Domain('active', 'in', [False]).optimize(IrRule))
        assert result.operator == 'not in'
        assert list(result.value) == [True]

    def test_a_single_false_under_not_in_flips_to_in(self):
        result = _sole(Domain('active', 'not in', [False]).optimize(IrRule))
        assert result.operator == 'in'
        assert list(result.value) == [True]

    def test_true_is_left_alone(self):
        result = _sole(Domain('active', 'in', [True]).optimize(IrRule))
        assert result.operator == 'in'
        assert list(result.value) == [True]

    def test_the_comparison_is_always_against_true(self):
        """La fuente lo declara: *"it eases the implementation of search methods"*.

        Un solo caso que atender en el compilador de hoja, en vez de dos
        simetricos. Por eso ``in [False]`` no se compila: se invierte.
        """
        for operator, value in (('in', [False]), ('not in', [False])):
            result = _sole(Domain('active', operator, value).optimize(IrRule))
            assert list(result.value) == [True], (operator, value)


class TestBothBooleansIsATautology:
    """``b in [True, False]`` es siempre verdadero — pero solo en FULL.

    La fuente lo acota a ese nivel a proposito, y lo comenta: la
    simplificacion *"removes fields (like active) from the domain"*, asi que
    hacerla antes la aplicaria tambien a un subdominio, donde ese campo
    todavia hace falta.
    """

    def test_at_full_level_it_collapses_to_true(self):
        assert Domain('active', 'in', [True, False]).optimize_full(
            IrRule) == Domain.TRUE

    def test_not_in_both_collapses_to_false(self):
        assert Domain('active', 'not in', [True, False]).optimize_full(
            IrRule) == Domain.FALSE

    def test_at_the_basic_level_the_field_survives(self):
        """El control del recorte: en BASIC la condicion NO desaparece.

        Este caso es el que distingue *"la tautologia se simplifica"* de
        *"el campo se pierde"*. Si el optimizador se registrara en BASIC,
        pasaria igual y nadie notaria que ``active`` desaparecio de un
        subdominio que lo necesitaba.
        """
        optimized = Domain('active', 'in', [True, False]).optimize(IrRule)
        assert isinstance(optimized, DomainCondition)
        assert optimized.field_expr == 'active'


class TestThePatternMustBeAString:
    """``_optimize_like_str`` — el valor de un ``like`` se valida como texto."""

    def test_a_number_becomes_its_string(self):
        result = _sole(Domain('name', 'like', 3).optimize(IrRule))
        assert result.value == '3'

    def test_a_string_is_left_alone(self):
        result = _sole(Domain('name', 'like', 'ab').optimize(IrRule))
        assert result.value == 'ab'
        assert result.operator == 'like'

    def test_an_empty_pattern_on_a_scalar_becomes_a_boolean(self):
        """``like ''`` casa con todo, asi que colapsa sin mirar la columna."""
        assert Domain('name', 'like', '').optimize(IrRule) == Domain.TRUE

    def test_an_empty_pattern_under_not_like_is_false(self):
        assert Domain('name', 'not like', '').optimize(IrRule) == Domain.FALSE

    def test_an_empty_pattern_on_a_relation_asks_the_column(self):
        """El ramal que ``relational`` gobierna, y que valia ``False``.

        En un campo relacional el patron vacio NO colapsa a booleano: se
        traduce a una comparacion contra la columna, porque el resultado
        depende de si hay valor o no.
        """
        result = Domain('groups', 'like', '').optimize(IrRule)
        assert result != Domain.TRUE
        assert result != Domain.FALSE

    def test_an_equal_like_asks_the_column_even_on_a_scalar(self):
        """``=like`` casa solo con la cadena vacia, no con todo."""
        result = Domain('name', '=like', '').optimize(IrRule)
        assert result != Domain.TRUE
        assert result != Domain.FALSE

    def test_an_equal_like_with_a_non_string_raises(self):
        with pytest.raises(TypeError):
            Domain('name', '=like', 3).optimize(IrRule)

    def test_a_plain_like_with_a_non_string_does_not_raise(self):
        """El control de la asimetria: solo el ``=``-like exige texto.

        Sin este caso, el test anterior no distinguiria *"``=like`` levanta"*
        de *"todo ``like`` con un no-texto levanta"*.
        """
        assert _sole(Domain('name', 'like', 3).optimize(IrRule)).value == '3'
