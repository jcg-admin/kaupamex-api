"""El AST de dominios — ``orm/domains.py`` (≙ ``odoo19c: odoo/orm/domains.py``).

Cubre los cuatro defectos que :ref:`h-api-613` y :ref:`h-api-614` registraron, y
las propiedades del AST que los hacen imposibles de reintroducir: el álgebra
booleana, el parseo de la notación polaca y el empuje de la negación a las
hojas.

El eje del archivo es la **semántica ante NULL**. La forma de la fuente incluye
la fila sin valor al negar; la de Django la descarta. Los tests de SQL emitido
lo comparan contra PostgreSQL real, que es donde la diferencia se observa.
"""
import pytest
from django.db import connection
from django.db.models import Q

from orm.domains import (
    AND,
    FALSE_DOMAIN,
    NOT,
    OR,
    TRUE_DOMAIN,
    Domain,
    DomainAnd,
    DomainBool,
    DomainCondition,
    DomainNot,
    DomainOr,
    OptimizationLevel,
    to_q,
)
from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups


def sql_of(queryset):
    """El WHERE que el queryset emite, en texto."""
    return str(queryset.query)


# === El AST: construcción y álgebra ========================================

class TestDomainConstruction:
    """``Domain()`` como fábrica — ≙ ``domains.py:206``."""

    def test_empty_list_is_the_true_domain(self):
        assert Domain([]) is Domain.TRUE
        assert Domain(True) is Domain.TRUE

    def test_false_builds_the_false_domain(self):
        assert Domain(False) is Domain.FALSE

    def test_true_leaf_collapses_to_the_true_domain(self):
        """``(1, '=', 1)`` es el leaf VERDADERO de la fuente."""
        assert Domain([(1, '=', 1)]) is Domain.TRUE

    def test_false_leaf_collapses_to_the_false_domain(self):
        """``(0, '=', 1)`` es el leaf FALSO — el que reventaba (H-API-613)."""
        assert Domain([(0, '=', 1)]) is Domain.FALSE

    def test_single_condition_builds_a_condition_node(self):
        domain = Domain([('name', '=', 'x')])
        assert isinstance(domain, DomainCondition)
        assert (domain.field_expr, domain.operator, domain.value) == ('name', '=', 'x')

    def test_implicit_and_between_consecutive_conditions(self):
        domain = Domain([('a', '=', 1), ('b', '=', 2)])
        assert isinstance(domain, DomainAnd)
        assert len(domain.children) == 2

    def test_polish_notation_is_parsed_with_its_operators(self):
        domain = Domain(['|', ('a', '=', 1), ('b', '=', 2)])
        assert isinstance(domain, DomainOr)

    def test_negation_operator_is_parsed(self):
        domain = Domain(['!', ('a', '=', 1)])
        assert isinstance(domain, DomainCondition)
        assert domain.operator == '!='

    def test_malformed_domain_raises(self):
        with pytest.raises(ValueError):
            Domain(['&', ('a', '=', 1)])

    def test_invalid_operator_raises(self):
        with pytest.raises(ValueError):
            Domain([('a', 'no-existe', 1)])

    def test_domain_objects_are_immutable(self):
        domain = Domain([('a', '=', 1)])
        with pytest.raises(TypeError):
            domain.operator = '!='

    def test_round_trip_through_the_polish_list(self):
        """``list(domain)`` devuelve la notación polaca — ≙ ``__iter__``."""
        source = ['|', ('a', '=', 1), ('b', '=', 2)]
        assert list(Domain(source)) == source


class TestDomainAlgebra:
    """El álgebra booleana de los nodos."""

    def test_true_is_the_neutral_element_of_and(self):
        condition = Domain([('a', '=', 1)])
        assert (Domain.TRUE & condition) is condition

    def test_false_absorbs_and(self):
        condition = Domain([('a', '=', 1)])
        assert (Domain.FALSE & condition) is Domain.FALSE

    def test_false_is_the_neutral_element_of_or(self):
        condition = Domain([('a', '=', 1)])
        assert (Domain.FALSE | condition) is condition

    def test_true_absorbs_or(self):
        condition = Domain([('a', '=', 1)])
        assert (Domain.TRUE | condition) is Domain.TRUE

    def test_double_negation_returns_the_child(self):
        condition = Domain([('a', 'any', [])])
        assert ~(~condition) == condition

    def test_nested_ands_are_flattened(self):
        domain = Domain.AND([
            Domain.AND([Domain([('a', '=', 1)]), Domain([('b', '=', 2)])]),
            Domain([('c', '=', 3)]),
        ])
        assert isinstance(domain, DomainAnd)
        assert len(domain.children) == 3

    def test_inverse_of_and_is_or(self):
        assert DomainAnd.INVERSE is DomainOr
        assert DomainOr.INVERSE is DomainAnd

    def test_de_morgan_on_a_nary(self):
        domain = Domain(['|', ('a', '=', 1), ('b', '=', 2)])
        assert isinstance(~domain, DomainAnd)

    def test_bool_keeps_the_historic_semantics(self):
        """Sólo el dominio ``[]`` era falso."""
        assert not Domain([])
        assert Domain([('a', '=', 1)])


class TestNegationReachesTheLeaves:
    """El empuje de la negación — ≙ ``DomainNot._optimize_step``."""

    def test_optimizing_a_negation_inverts_the_operator(self):
        domain = Domain(['!', ('a', 'in', [1, 2])]).optimize()
        assert isinstance(domain, DomainCondition)
        assert domain.operator == 'not in'

    def test_optimizing_a_negated_or_applies_de_morgan(self):
        """El OR negado pasa a AND y cada hijo invierte su operador.

        Desde ``api@d7f4b8e4`` el operador invertido no se queda en ``!=``:
        ``_operator_equal_as_in`` lo reduce a ``not in``, que es lo que la
        fuente promete al compilador de hoja. Antes de ese optimizador la
        reducción ocurría en la compilación, así que el dominio optimizado
        conservaba el ``!=`` — este caso lo asertaba, y encodificaba la
        AUSENCIA del optimizador, no el contrato.
        """
        domain = Domain(['!', '|', ('a', '=', 1), ('b', '=', 2)]).optimize()
        assert isinstance(domain, DomainAnd)
        assert all(child.operator == 'not in' for child in domain.children)

    def test_a_negated_inequality_adds_its_null_branch(self):
        """Sin valor *falsy*, ``NOT (a < v)`` debe incluir la fila sin valor."""
        domain = Domain(['!', ('a', '<', 5)]).optimize()
        assert isinstance(domain, DomainOr)
        operators = {child.operator for child in domain.children}
        assert operators == {'in', '>='}

    def test_a_dotted_path_is_not_inverted(self):
        """Conservador con las rutas, igual que la fuente: to-many difiere."""
        domain = Domain(['!', ('a.b', '=', 1)]).optimize()
        assert isinstance(domain, DomainNot)

    def test_optimize_reaches_a_fixed_point(self):
        domain = Domain(['!', '!', ('a', '=', 1)])
        assert domain.optimize()._opt_level >= OptimizationLevel.BASIC


# === La compilación a Q =====================================================

class TestCompilationToQ:
    """``_to_q`` — la forma del filtro, sin tocar la base."""

    def test_the_true_domain_compiles_to_an_empty_q(self):
        assert to_q([]) == Q()

    def test_the_false_domain_compiles_to_the_empty_set(self):
        """``Q(pk__in=[])``, no ``~Q()`` — el defecto de H-API-606."""
        assert to_q([(0, '=', 1)]) == Q(pk__in=[])

    def test_equality_normalizes_to_in(self):
        """≙ ``_operator_equal_as_in``, que allá es un optimizador."""
        assert to_q([('name', '=', 'x')]) == Q(name__in=['x'])

    def test_equality_against_false_becomes_a_null_check(self):
        assert to_q([('name', '=', False)]) == Q(name__isnull=True)

    def test_a_dotted_path_uses_the_django_traversal(self):
        """H-API-614: ``a.b`` no lo resuelve Django, ``a__b`` sí."""
        compiled = to_q([('picking_id.picking_type_id', '=', 3)])
        assert compiled == Q(picking_id__picking_type_id__in=[3])

    def test_the_four_pattern_operators_exist(self):
        """H-API-613 defecto 3: ``=like`` y familia no existían."""
        for operator in ('=like', 'not =like', '=ilike', 'not =ilike'):
            assert to_q([('name', operator, 'x%')]) is not None

    def test_a_raw_pattern_keeps_its_wildcards(self):
        """``=like`` NO envuelve: el patrón lo pone quien escribe el dominio."""
        assert to_q([('name', '=like', 'x%')]) == Q(name__sql_like='x%')

    def test_like_wraps_the_value_in_wildcards(self):
        assert to_q([('name', 'like', 'x')]) == Q(name__sql_like='%x%')

    def test_an_unsupported_operator_raises_at_compile_time(self):
        """El constructor lo rechaza, y la compilación es la segunda red.

        ``DomainCondition`` es el init interno: no valida. Quien valida es
        ``checked()``, y ``_to_q`` vuelve a comprobar porque un nodo puede
        llegar ahí sin haber pasado por la fábrica.
        """
        with pytest.raises(ValueError):
            DomainCondition('a', 'no-existe', 1).checked()
        with pytest.raises(ValueError):
            DomainCondition('a', 'no-existe', 1)._to_q()


class TestTheNullRule:
    """La semántica ante NULL — corregida por medición (:ref:`h-api-614`).

    La premisa de la iniciativa decía que Django pierde la fila sin valor al
    negar. **Es falso:** su compilador añade ``AND col IS NOT NULL`` dentro de
    la negación, con lo que la fila entra, igual que en la fuente. Lo que sí
    diverge es el caso contrario: donde la fuente **excluye** la fila sin valor,
    Django la incluiría.
    """

    def test_a_negative_equality_relies_on_the_django_guard(self):
        """Sin rama añadida a mano: ``~Q`` ya trae la suya."""
        assert to_q([('name', '!=', 'x')]) == ~Q(name__in=['x'])

    def test_a_negative_pattern_relies_on_the_django_guard(self):
        assert to_q([('name', 'not like', 'x')]) == ~Q(name__sql_like='%x%')

    def test_a_positive_pattern_is_a_plain_condition(self):
        assert to_q([('name', 'like', 'x')]) == Q(name__sql_like='%x%')

    def test_in_with_false_adds_the_null_branch(self):
        """``in {x, False}`` es «vale x o no tiene valor» — ahí sí se añade."""
        assert to_q([('name', 'in', ['x', False])]) == (
            Q(name__in=['x']) | Q(name__isnull=True))

    def test_not_in_with_false_excludes_the_unset_rows(self):
        """La divergencia real: la fuente excluye la fila sin valor.

        ``not in {x, False}`` significa «tiene valor y no es x». El ``~Q`` de
        Django la incluiría, así que se fuerza con ``isnull=False``.
        """
        assert to_q([('name', 'not in', ['x', False])]) == (
            ~Q(name__in=['x']) & Q(name__isnull=False))

    def test_not_in_only_false_asks_for_a_set_value(self):
        assert to_q([('name', 'not in', [False])]) == Q(name__isnull=False)

    def test_a_non_nullable_field_needs_no_forcing(self):
        """Con el modelo, ``field.null`` decide — ≙ ``can_be_null``.

        Y el ``''`` que aparece en la lista no es ruido: ``IrRule.name`` es un
        ``CharField``, cuyo *falsy value* es la cadena vacía
        (``odoo19c: fields_textual.py:38``). La fuente lo añade a los
        parámetros cuando la colección traía ``False``
        (``fields.py:1288-1292``), porque para ese campo «sin valor» y «cadena
        vacía» son lo mismo.
        """
        compiled = to_q([('name', 'not in', ['x', False])], model=IrRule)
        assert compiled == ~Q(name__in=['x', ''])

    def test_the_falsy_value_of_the_field_joins_the_parameters(self):
        """El mismo mecanismo sobre un entero, y con columna nulable.

        ``ResGroups.sequence`` es ``IntegerField(null=True)``: su *falsy value*
        es ``0`` y además hace falta el ``isnull=False`` que excluye la fila sin
        valor.
        """
        compiled = to_q([('sequence', 'not in', [5, False])], model=ResGroups)
        assert compiled == (~Q(sequence__in=[5, 0]) & Q(sequence__isnull=False))


@pytest.mark.django_db
class TestEmittedSql:
    """El SQL que PostgreSQL recibe — la comparación contra la fuente.

    La fuente emite ``(cond OR campo IS NULL)`` para un operador negativo sobre
    columna nulable (``odoo19c: odoo/orm/fields.py:1331-1333``). Django emite
    ``NOT (cond AND campo IS NOT NULL)``. Estos tests verifican que las dos
    formas coinciden en el conjunto de filas, que es lo que importa.
    """

    def test_django_emits_its_own_null_guard(self):
        """La medición que corrigió la premisa (:ref:`h-api-614`)."""
        sql = sql_of(ResGroups.objects.filter(to_q([('user_type', 'not like', 'x')])))
        assert 'IS NOT NULL' in sql, 'Django añade la guarda dentro de la negación'
        assert 'NOT (' in sql

    def test_a_non_nullable_column_gets_no_guard(self):
        sql = sql_of(ResGroups.objects.filter(to_q([('name', 'not like', 'x')])))
        assert 'IS NOT NULL' not in sql

    def test_the_raw_like_reaches_postgresql_as_like(self):
        sql = sql_of(IrRule.objects.filter(to_q([('name', '=like', 'a%')])))
        assert 'LIKE' in sql

    def test_the_raw_ilike_reaches_postgresql_as_ilike(self):
        sql = sql_of(IrRule.objects.filter(to_q([('name', '=ilike', 'a%')])))
        assert 'ILIKE' in sql

    def test_both_forms_agree_on_the_null_row(self):
        """Las dos escrituras de la misma regla, contra el motor.

        Si esta aserción cae, una de las dos formas dejó de incluir la fila sin
        valor y la regla de fila concede o niega visibilidad distinta de la que
        declara.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT ((NULL LIKE 'X') OR NULL IS NULL)")
            reference_form = cursor.fetchone()[0]
            cursor.execute("SELECT NOT ((NULL LIKE 'X') AND NULL IS NOT NULL)")
            django_form = cursor.fetchone()[0]
        assert reference_form is True
        assert django_form is True

    def test_a_negated_domain_keeps_the_row_without_value(self):
        """De extremo a extremo, sobre filas reales.

        ``ResGroups.user_type`` es la columna nulable que el árbol ofrece
        (``null=True``); es lo que hace observable la diferencia.
        """
        with_value = ResGroups.objects.create(name='con-valor', user_type='portal')
        without_value = ResGroups.objects.create(name='sin-valor', user_type=None)

        found = set(
            ResGroups.objects
            .filter(to_q([('user_type', 'not like', 'nunca-coincide')]))
            .values_list('pk', flat=True)
        )
        assert with_value.pk in found
        assert without_value.pk in found, 'la fila sin valor debe entrar'

    def test_not_in_with_false_drops_the_row_without_value(self):
        """El contrafactual del caso que SÍ diverge.

        Sin el ``isnull=False`` que ``condition_to_q`` añade, el ``~Q`` de
        Django incluiría la fila sin valor y ``not in {x, False}`` dejaría de
        significar «tiene valor y no es x».
        """
        with_value = ResGroups.objects.create(name='con-valor', user_type='portal')
        without_value = ResGroups.objects.create(name='sin-valor', user_type=None)

        found = set(
            ResGroups.objects
            .filter(to_q([('user_type', 'not in', ['portal', False])]))
            .values_list('pk', flat=True)
        )
        assert with_value.pk not in found
        assert without_value.pk not in found, 'la fila sin valor NO debe entrar'

        naive = set(
            ResGroups.objects
            .filter(~Q(user_type__in=['portal']))
            .values_list('pk', flat=True)
        )
        assert without_value.pk in naive, 'el ~Q pelado sí la incluye'


# === La fachada sobre Q =====================================================

class TestQFacade:
    """``AND``/``OR``/``NOT`` sobre ``Q`` — el contrato que el árbol consume."""

    def test_and_of_nothing_is_the_true_domain(self):
        assert AND([]) == TRUE_DOMAIN

    def test_or_of_nothing_is_the_false_domain(self):
        assert OR([]) == FALSE_DOMAIN

    def test_and_combines_q_objects(self):
        assert AND([Q(a=1), Q(b=2)]) == (Q() & Q(a=1) & Q(b=2))

    def test_or_combines_q_objects(self):
        assert OR([Q(a=1), Q(b=2)]) == (Q(a=1) | Q(b=2))

    def test_not_negates_a_q_object(self):
        assert NOT(Q(a=1)) == ~Q(a=1)

    def test_the_false_domain_is_the_empty_set_not_its_opposite(self):
        """H-API-606: ``~Q(pk__in=[])`` colapsaba al queryset entero."""
        assert FALSE_DOMAIN == Q(pk__in=[])
