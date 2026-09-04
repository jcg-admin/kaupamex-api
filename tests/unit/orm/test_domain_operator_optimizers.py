"""Los optimizadores de operador — la primera familia de las cuatro.

El registro existe desde ``api@d7f4b8e4``; esta es la primera tanda de
optimizadores concretos que se cuelgan de el (tarea #225).

La familia normaliza el operador **antes** de compilar, que es lo que la
fuente promete al compilador de hoja. Hasta ahora ese trabajo lo hacia
``DomainCondition._normalized`` a mano, en el paso de compilacion, y el
docstring de ese metodo lo declaraba: *"en la fuente ese trabajo lo hacen los
optimizadores registrados, antes de que ninguno de los dos corra"*.

Cierra ademas la deuda de ``CONDITION_OPERATORS``: los cuatro operadores extra
—``=``, ``!=``, ``<>``, ``==``— estaban escritos **a mano** en esa constante
porque sin sus optimizadores el constructor los rechazaria. Ahora los declara
cada ``@operator_optimization``, como la fuente.
"""
import warnings

import pytest

from orm.domains import (
    CONDITION_OPERATORS,
    Domain,
    DomainCondition,
)
from tools.misc import OrderedSet


def _sole(domain):
    """La unica condicion del dominio, para asertar sobre ella."""
    conditions = list(domain.iter_conditions())
    assert len(conditions) == 1, f'se esperaba una condicion, hay {len(conditions)}'
    return conditions[0]


class TestEqualIfValue:
    """``=?`` — *"a =? b  <=>  not b or a = b"*, verbatim de la fuente."""

    def test_the_operator_is_now_constructible(self):
        assert '=?' in CONDITION_OPERATORS

    def test_a_falsy_value_makes_the_condition_true(self):
        assert DomainCondition('name', '=?', False).optimize().is_true()

    def test_an_empty_string_makes_it_true_too(self):
        assert DomainCondition('name', '=?', '').optimize().is_true()

    def test_a_truthy_value_becomes_a_plain_equality(self):
        result = _sole(DomainCondition('name', '=?', 'a').optimize())
        assert result.operator == 'in'
        assert list(result.value) == ['a']


class TestTheDeprecatedSpellings:
    """``<>`` y ``==`` — reescrituras con aviso, como la fuente."""

    def test_the_diamond_becomes_not_equal(self):
        with pytest.warns(DeprecationWarning, match="'<>'"):
            result = _sole(DomainCondition('name', '<>', 'a').optimize())
        assert result.operator == 'not in'

    def test_the_double_equal_becomes_equal(self):
        with pytest.warns(DeprecationWarning, match="'=='"):
            result = _sole(DomainCondition('name', '==', 'a').optimize())
        assert result.operator == 'in'

    def test_both_carry_their_value_through(self):
        with pytest.warns(DeprecationWarning):
            result = _sole(DomainCondition('name', '==', 'valor').optimize())
        assert list(result.value) == ['valor']


class TestEqualityAsMembership:
    """``=``/``!=`` pasan a ``in``/``not in`` — ≙ ``_operator_equal_as_in``."""

    def test_equal_becomes_in(self):
        assert _sole(DomainCondition('name', '=', 'a').optimize()).operator == 'in'

    def test_not_equal_becomes_not_in(self):
        assert _sole(DomainCondition('name', '!=', 'a').optimize()).operator == 'not in'

    def test_the_scalar_becomes_a_one_element_set(self):
        result = _sole(DomainCondition('name', '=', 'a').optimize())
        assert isinstance(result.value, OrderedSet)
        assert list(result.value) == ['a']

    def test_a_collection_is_kept_as_a_set(self):
        result = _sole(DomainCondition('name', '=', ['a', 'b']).optimize())
        assert list(result.value) == ['a', 'b']

    def test_an_empty_collection_compares_against_unset(self):
        """La fuente lo comenta verbatim: *"views sometimes use
        ``('user_ids', '!=', [])`` to indicate the user is set"*."""
        result = _sole(DomainCondition('user_ids', '!=', []).optimize())
        assert result.operator == 'not in'
        assert list(result.value) == [False]

    def test_a_repeated_value_appears_once(self):
        result = _sole(DomainCondition('name', '=', ['a', 'a', 'b']).optimize())
        assert list(result.value) == ['a', 'b']


class TestTheMembershipSet:
    """``in``/``not in`` — ≙ ``_optimize_in_set``."""

    def test_a_list_becomes_an_ordered_set(self):
        result = _sole(DomainCondition('name', 'in', ['a', 'b']).optimize())
        assert isinstance(result.value, OrderedSet)

    def test_an_empty_in_collapses_to_false(self):
        assert DomainCondition('name', 'in', []).optimize().is_false()

    def test_an_empty_not_in_collapses_to_true(self):
        assert DomainCondition('name', 'not in', []).optimize().is_true()

    def test_a_scalar_is_wrapped_in_a_set(self):
        result = _sole(DomainCondition('name', 'in', 'a').optimize())
        assert list(result.value) == ['a']

    def test_a_domain_value_switches_to_the_any_operator(self):
        """La travesia de relacion no es pertenencia: es ``any``."""
        result = _sole(
            DomainCondition('partner_id', 'in', Domain('name', '=', 'a')).optimize())
        assert result.operator == 'any'

    def test_a_domain_value_under_not_in_switches_to_not_any(self):
        result = _sole(
            DomainCondition('partner_id', 'not in', Domain('name', '=', 'a')).optimize())
        assert result.operator == 'not any'

    def test_an_ordered_set_is_returned_unchanged(self):
        """La fuente lo declara: *"very common case, just skip creation of a
        new Domain instance"*. Se asierta por IDENTIDAD, no por igualdad.
        """
        condition = DomainCondition('name', 'in', OrderedSet(['a']))
        assert _sole(condition.optimize()) is condition


class TestTheHandWrittenDebtIsGone:
    """Control discriminante: los cuatro extra ya no se declaran a mano.

    Si alguien vuelve a escribirlos en la constante y retira sus
    optimizadores, este caso sigue verde — mide la constante, no el registro.
    Por eso el que discrimina es el de abajo: mide que el operador **llega a
    optimizarse**, que es lo que un literal escrito a mano no consigue.
    """

    def test_the_four_are_constructible(self):
        for operator in ('=', '!=', '<>', '=='):
            assert operator in CONDITION_OPERATORS, operator

    def test_none_of_the_four_survives_the_optimization(self):
        """Ninguno queda en el dominio optimizado: los cuatro se reescriben.

        Este es el caso que cae si un optimizador desaparece — el operador
        seguiria siendo construible y llegaria intacto al compilador de hoja,
        que es exactamente lo que la fuente promete que no pasa.
        """
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            for operator in ('=', '!=', '<>', '=='):
                result = _sole(DomainCondition('name', operator, 'a').optimize())
                assert result.operator in ('in', 'not in'), (operator, result.operator)
