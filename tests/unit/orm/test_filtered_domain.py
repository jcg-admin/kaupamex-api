"""``filtered_domain`` — evaluar un dominio en memoria, sin ir al motor.

Cubre las tres piezas que la evaluación necesita y que se construyeron juntas:
``Field.expression_getter``/``Field.filter_function`` (``orm/fields.py``),
``Domain._as_predicate`` en las cinco clases del AST (``orm/domains.py``) y
``filtered_domain`` (``orm/models.py``).

Por qué el mismo dominio se mide en las dos vías
================================================

La clase :class:`TestBothCompilersAgree` corre cada dominio **dos veces**: una
contra PostgreSQL con ``filter(Domain(...)._to_q(...))`` y otra en memoria con
``filtered_domain``. Que las dos coincidan es lo único que impide que los dos
compiladores diverjan sobre el mismo dominio — y pueden: comparten la
normalización (``_normalized``) pero no el resto del camino.

Un test que sólo comprobara la vía en memoria sería el verde que no
discrimina: pasaría igual si el predicado interpretara ``ilike`` como ``like``,
porque nada lo estaría contrastando con la semántica que el motor aplica.
"""
import pytest
from django.db import models as django_models

from addons.base.models import ResPartner
from orm.domains import NEGATIVE_CONDITION_OPERATORS as DOMAINS_NEGATIVE_OPERATORS
from orm.domains import Domain
from orm.fields import NEGATIVE_CONDITION_OPERATORS as FIELDS_NEGATIVE_OPERATORS
from orm.models import AccessQuerySet, filtered_domain


#: Los dominios que las dos vías tienen que resolver igual. Cada uno nombra el
#: operador que ejercita, para que un fallo diga cuál cayó.
DOMAINS = [
    ('igualdad',            [('name', '=', 'Beta')]),
    ('desigualdad',         [('name', '!=', 'Beta')]),
    ('in',                  [('name', 'in', ['Alfa', 'Beta'])]),
    ('not in',              [('name', 'not in', ['Beta'])]),
    ('like',                [('name', 'like', 'Al%')]),
    ('ilike',               [('name', 'ilike', 'al%')]),
    ('=like exacto',        [('name', '=like', 'Alfa')]),
    # El acentuado va con el acento en el patrón: el ``ilike`` de este árbol
    # NO ignora acentos (``UNACCENT_ENABLED``), y el caso está abajo con su
    # propio test para que la decisión quede medida y no supuesta.
    ('ilike con acento',    [('name', 'ilike', 'ácme')]),
    ('and',                 ['&', ('name', '=', 'Alfa'), ('active', '=', True)]),
    ('or',                  ['|', ('name', '=', 'Alfa'), ('name', '=', 'Beta')]),
    ('not',                 ['!', ('name', '=', 'Beta')]),
    ('or anidado en and',   ['&', ('active', '=', True),
                             '|', ('name', '=', 'Alfa'), ('name', '=', 'Ácme')]),
]


@pytest.fixture
def partners(db):
    """Tres contactos, uno de ellos con acento para ejercitar ``ilike``."""
    return [
        ResPartner.objects.create(name='Alfa', active=True),
        ResPartner.objects.create(name='Beta', active=True),
        ResPartner.objects.create(name='Ácme', active=False),
    ]


def _names(records):
    return sorted(record.name for record in records)


@pytest.mark.django_db
class TestBothCompilersAgree:
    """El mismo dominio, resuelto por PostgreSQL y en memoria, coincide."""

    @pytest.mark.parametrize('label,domain', DOMAINS, ids=[d[0] for d in DOMAINS])
    def test_the_engine_and_the_predicate_return_the_same_rows(
            self, partners, label, domain):
        ids = [partner.pk for partner in partners]
        from_engine = ResPartner.objects.filter(pk__in=ids).filter(
            Domain(domain)._to_q(ResPartner))
        in_memory = filtered_domain(partners, domain)
        assert _names(in_memory) == _names(from_engine), label


@pytest.mark.django_db
class TestFilteredDomain:
    def test_it_keeps_the_order_of_the_input(self, partners):
        reversed_input = list(reversed(partners))
        result = filtered_domain(reversed_input, [('active', '=', True)])
        assert [record.name for record in result] == ['Beta', 'Alfa']

    def test_an_empty_domain_returns_everything(self, partners):
        assert len(filtered_domain(partners, [])) == 3

    def test_no_records_is_a_no_op(self):
        assert filtered_domain([], [('name', '=', 'Alfa')]) == []

    def test_it_reaches_an_unsaved_record(self):
        """El caso que motivó construirlo: un registro que no está en la base.

        Es lo que ``_evaluate_condition_with_fallback`` necesita — el valor de
        respaldo de un campo dependiente de empresa no vive en ninguna fila.
        """
        unsaved = ResPartner(name='Sin guardar')
        assert unsaved.pk is None
        assert len(filtered_domain([unsaved], [('name', '=', 'Sin guardar')])) == 1
        assert filtered_domain([unsaved], [('name', '=', 'Otra')]) == []

    def test_the_queryset_method_delegates_to_the_function(self, partners):
        """El método de ``AccessQuerySet``, construido a mano.

        Ningún modelo declara todavía ``objects = AccessManager()`` (tarea
        **#96**), así que el queryset se instancia directo en vez de fingir
        que ya se puede llegar por ``.objects``.
        """
        rows = AccessQuerySet(model=ResPartner).filter(
            pk__in=[partner.pk for partner in partners])
        assert _names(rows.filtered_domain([('active', '=', True)])) == [
            'Alfa', 'Beta']

    def test_it_returns_a_list_not_a_queryset(self, partners):
        rows = AccessQuerySet(model=ResPartner).filter(
            pk__in=[partner.pk for partner in partners])
        assert isinstance(rows.filtered_domain([('active', '=', True)]), list)


class TestAsPredicate:
    """El AST, sin base: cada clase construye su predicado."""

    def test_true_admits_every_record(self):
        assert Domain.TRUE._as_predicate(ResPartner)(ResPartner(name='X'))

    def test_false_admits_no_record(self):
        assert not Domain.FALSE._as_predicate(ResPartner)(ResPartner(name='X'))

    def test_an_empty_collection_collapses_to_a_constant(self):
        record = ResPartner(name='X')
        assert not Domain([('name', 'in', [])])._as_predicate(ResPartner)(record)
        assert Domain([('name', 'not in', [])])._as_predicate(ResPartner)(record)

    def test_without_a_model_it_refuses_instead_of_guessing(self):
        with pytest.raises(ValueError, match='Sin modelo'):
            Domain([('name', '=', 'X')])._as_predicate(None)

    def test_the_hierarchy_goes_up_to_full_before_being_evaluated(self, db):
        """``child_of`` no tiene predicado propio: se resuelve subiendo a
        ``FULL``, que es donde su optimizador lo reescribe a un dominio simple
        — ≙ ``odoo19c: :1045-1047``, con su *"TODO have a specific
        implementation for these"*.

        El caso **ejecuta** el predicado: hasta ``api@24b9b12c`` el operador ni
        siquiera existía en ``CONDITION_OPERATORS`` y este mismo caso afirmaba
        que ``checked()`` lo rechazaba. Comprobar sólo que no levanta lo dejaría
        pasar con la rama ausente, porque el rechazo también vendría de
        ``_normalized``: por eso se afirma sobre a quién acepta y a quién no.
        """
        padre = ResPartner.objects.create(name='Padre 967')
        hija = ResPartner.objects.create(name='Hija 967', parent=padre)
        ajena = ResPartner.objects.create(name='Ajena 967')
        predicado = Domain([('id', 'child_of', padre.pk)])._as_predicate(ResPartner)
        assert predicado(hija) and predicado(padre)
        assert not predicado(ajena)

    def test_a_relation_traversal_refuses_in_memory(self):
        with pytest.raises(NotImplementedError, match='travesía'):
            Domain([('parent', 'any', Domain([('name', '=', 'X')]))]
                   )._as_predicate(ResPartner)

    def test_a_custom_domain_without_predicate_says_so(self):
        custom = Domain.custom(to_q=lambda model: django_models.Q())
        with pytest.raises(ValueError, match='predicate='):
            custom._as_predicate(ResPartner)

    def test_a_custom_domain_uses_the_predicate_it_was_given(self):
        custom = Domain.custom(
            to_q=lambda model: django_models.Q(),
            predicate=lambda record: record.name == 'sí')
        assert custom._as_predicate(ResPartner)(ResPartner(name='sí'))
        assert not custom._as_predicate(ResPartner)(ResPartner(name='no'))


class TestUnaccentDecisionIsShared:
    """El ``ilike`` en memoria decide lo mismo que ``sql_ilike``.

    Mientras ``UNACCENT_ENABLED`` sea falso —lo es: la extensión ``unaccent``
    no está instalada, y ``SqlILike`` emite un ``ILIKE`` pelado— buscar «acme»
    **no** encuentra «Ácme», en ninguna de las dos vías. Cuando la tarea #98
    instale la extensión, las dos cambian juntas.
    """

    @pytest.mark.django_db
    def test_neither_way_ignores_the_accent(self, partners):
        domain = [('name', 'ilike', 'acme')]
        from_engine = ResPartner.objects.filter(
            pk__in=[p.pk for p in partners]).filter(
                Domain(domain)._to_q(ResPartner))
        assert _names(filtered_domain(partners, domain)) == _names(from_engine)
        assert list(from_engine) == []


class TestFilterFunction:
    """``Field.filter_function`` — el compilador de hoja en memoria."""

    def _field(self, name='name'):
        return ResPartner._meta.get_field(name)

    def test_it_refuses_a_negative_operator(self):
        with pytest.raises(ValueError, match='operador positivo'):
            self._field().filter_function(ResPartner, 'name', 'not in', {'x'})

    def test_in_with_an_empty_collection_refuses(self):
        with pytest.raises(ValueError, match='colección no vacía'):
            self._field().filter_function(ResPartner, 'name', 'in', [])

    def test_an_unknown_operator_refuses(self):
        with pytest.raises(NotImplementedError, match='Operador simple'):
            self._field().filter_function(ResPartner, 'name', '=?', 'x')

    def test_the_getter_refuses_an_expression_it_cannot_read(self):
        with pytest.raises(ValueError, match='Expression not supported'):
            self._field().expression_getter('name.month_number')

    def test_the_like_pattern_escapes_the_regex_metacharacters(self):
        """``.`` en el patrón es un punto literal, no «cualquier carácter»."""
        function = self._field().filter_function(
            ResPartner, 'name', '=like', 'a.c')
        assert function(ResPartner(name='a.c'))
        assert not function(ResPartner(name='abc'))

    def test_the_backslash_escapes_the_sql_wildcard(self):
        function = self._field().filter_function(
            ResPartner, 'name', '=like', r'100\%')
        assert function(ResPartner(name='100%'))
        assert not function(ResPartner(name='100X'))

    def test_underscore_matches_exactly_one_character(self):
        function = self._field().filter_function(
            ResPartner, 'name', '=like', 'a_c')
        assert function(ResPartner(name='abc'))
        assert not function(ResPartner(name='ac'))


class TestNegativeOperatorsStayInSync:
    """La copia de ``orm/fields.py`` contra la original de ``orm/domains.py``.

    ``fields.py`` lleva su propio ``NEGATIVE_CONDITION_OPERATORS`` porque
    importar el de ``domains`` cerraría un ciclo (tarea #380). Dos copias que
    nadie contrasta divergen en silencio; esto es lo que lo impide.
    """

    def test_the_copy_covers_the_same_operators(self):
        assert set(DOMAINS_NEGATIVE_OPERATORS) == set(FIELDS_NEGATIVE_OPERATORS)
