"""El camino de búsqueda de un campo — ``search=`` y su despachador.

≙ ``odoo19c: odoo/orm/domains.py:986`` (``_optimize_field_search_method``),
``odoo/orm/fields.py:1926`` (``Field.determine_domain``) y ``:66``
(``determine``).

La cadena es la que :ref:`h-api-964` midió: una condición sobre un campo que
declara ``search=`` no se compila a SQL —no tiene columna— sino que **se
sustituye** por el dominio que su método devuelve. Ese dominio se compone con
el resto igual que cualquier otro, que es lo que un ``QuerySet`` no puede
hacer.
"""
import inspect

import pytest

from orm.domains import Domain, to_q
from orm.fields import _FIELD_CLASS_ATTRIBUTES, determine
from orm.fields_nonstored import NonStored

from addons.base.models.ir_config_parameter import SystemParameter


pytestmark = pytest.mark.django_db


@pytest.fixture
def config_parameter():
    return SystemParameter


class _Recordset:
    """Sustituto mínimo de un recordset para ejercitar ``determine``."""

    def method_by_name(self, *args):
        return ('por-nombre', args)


class TestDetermine:
    """``determine`` — el invocable o el nombre de método, ≙ ``fields.py:66``."""

    def test_resolves_a_method_given_by_name(self):
        records = _Recordset()
        assert determine('method_by_name', records, 'a', 'b') == (
            'por-nombre', ('a', 'b'))

    def test_resolves_a_plain_callable_passing_the_records(self):
        def searcher(records, operator, value):
            return ('invocable', records, operator, value)

        records = _Recordset()
        assert determine(searcher, records, 'in', [1]) == (
            'invocable', records, 'in', [1])

    def test_rejects_something_that_is_neither(self):
        with pytest.raises(TypeError):
            determine(42, _Recordset())


class TestNonStoredSearch:
    """``NonStored`` acepta ``search=`` y lo expone como el campo de la fuente."""

    def test_the_descriptor_keeps_the_search_method(self):
        field = NonStored(default=None, search='_buscar')
        assert field.search == '_buscar'

    def test_without_search_the_attribute_is_none(self):
        assert NonStored(default=None).search is None

    def test_determine_domain_delegates_to_the_search_method(self, config_parameter):
        field = NonStored(default=None,
                          search=lambda records, operator, value: Domain(
                              'key', operator, value))
        result = field.determine_domain(config_parameter, 'ilike', 'x')
        assert result == Domain('key', 'ilike', 'x')

    def test_determine_domain_without_search_is_not_implemented(self, config_parameter):
        assert NonStored(default=None).determine_domain(
            config_parameter, 'ilike', 'x') is NotImplemented


class TestFieldResolutionReachesTheNonStored:
    """``_field`` encuentra el descriptor que ``_meta`` no conoce.

    Es la divergencia de este árbol: la fuente guarda campos con y sin columna
    en el mismo ``_fields``; Django los reparte entre ``_meta`` (los que tienen
    columna) y atributos de clase (los que no).
    """

    def test_a_stored_field_still_resolves_through_meta(self, config_parameter):
        condition = Domain('key', '=', 'x')
        assert condition._field(config_parameter) is not None

    def test_the_non_stored_display_name_resolves(self, config_parameter):
        condition = Domain('display_name', 'ilike', 'x')
        field = condition._field(config_parameter)
        assert isinstance(field, NonStored)
        assert field.search is not None

    def test_a_name_that_is_neither_still_raises(self, config_parameter):
        with pytest.raises(ValueError):
            Domain('no_existe_en_ninguna_parte', '=', 1)._field(config_parameter)


class TestSearchDisplayNameReturnsADomain:
    """``_search_display_name`` devuelve un ``Domain``, no un ``QuerySet``.

    ≙ ``odoo19c: odoo/orm/models.py:1442``. La forma importa: un dominio se
    compone dentro de un ``any`` y un ``QuerySet`` no.
    """

    def test_the_result_is_a_domain(self, config_parameter):
        assert isinstance(
            config_parameter._search_display_name('ilike', 'x'), Domain)

    def test_it_searches_over_the_rec_name(self, config_parameter):
        assert config_parameter._search_display_name('ilike', 'x') == Domain(
            'key', 'ilike', 'x')

    def test_the_empty_like_short_circuit_is_kept(self, config_parameter):
        assert config_parameter._search_display_name('ilike', '') is Domain.TRUE

    def test_the_domain_still_compiles_to_a_queryset(self, config_parameter):
        config_parameter.objects.create(key='una.clave', value='v')
        domain = config_parameter._search_display_name('ilike', 'una.cl')
        found = config_parameter.objects.filter(
            to_q(domain, config_parameter))
        assert [p.key for p in found] == ['una.clave']


class TestTheConditionIsReplacedBySearch:
    """El consumidor real: la condición se sustituye por el dominio buscado."""

    def test_a_condition_on_display_name_becomes_the_search_domain(
            self, config_parameter):
        optimizado = Domain('display_name', 'ilike', 'abc').optimize(
            config_parameter)
        assert optimizado == Domain('key', 'ilike', 'abc').optimize(
            config_parameter)

    def test_the_replacement_composes_inside_a_conjunction(self, config_parameter):
        combined = (Domain('display_name', 'ilike', 'abc')
                     & Domain('value', '=', 'v')).optimize(config_parameter)
        expected = (Domain('key', 'ilike', 'abc')
                    & Domain('value', '=', 'v')).optimize(config_parameter)
        assert combined == expected

    def test_the_replaced_condition_reaches_the_database(self, config_parameter):
        config_parameter.objects.create(key='alfa.uno', value='1')
        config_parameter.objects.create(key='beta.dos', value='2')
        found = config_parameter.objects.filter(
            to_q(Domain('display_name', 'ilike', 'alfa'), config_parameter))
        assert [p.key for p in found] == ['alfa.uno']

    def test_a_stored_field_is_left_alone(self, config_parameter):
        condition = Domain('key', 'ilike', 'abc')
        assert condition.optimize(config_parameter) == condition.optimize(
            config_parameter)
        assert 'key' in repr(condition.optimize(config_parameter))


class TestTheFallbackLadder:
    """Las tres ramas de respaldo de ``_optimize_field_search_method``."""

    def test_a_negative_operator_retries_with_the_positive_and_negates(
            self, config_parameter):
        negative = Domain('display_name', 'not ilike', 'abc').optimize(
            config_parameter)
        positive = Domain('key', 'ilike', 'abc').optimize(config_parameter)
        assert negative == (~positive).optimize(config_parameter)

    def test_a_search_that_only_knows_equality_is_decomposed_for_in(
            self, config_parameter, monkeypatch):
        def only_equality(records, operator, value):
            if operator != '=':
                return NotImplemented
            return Domain('key', '=', value)

        descriptor = inspect.getattr_static(config_parameter, 'display_name')
        monkeypatch.setattr(descriptor, 'search', only_equality)
        result = Domain('display_name', 'in', ['a', 'b'])\
            ._optimize_field_search_method(config_parameter)
        assert result == Domain.OR([Domain('key', '=', 'a'),
                                       Domain('key', '=', 'b')])

    def test_a_search_that_supports_nothing_raises_naming_the_field(
            self, config_parameter, monkeypatch):
        descriptor = inspect.getattr_static(config_parameter, 'display_name')
        monkeypatch.setattr(descriptor, 'search',
                            lambda *_args: NotImplemented)
        with pytest.raises(ValueError, match='display_name'):
            Domain('display_name', 'ilike', 'x')\
                ._optimize_field_search_method(config_parameter)


class TestTheNonStoredAnswersTheFieldContract:
    """Un campo sin columna responde al contrato de campo — ≙ ``Field``.

    En la fuente ``NonStored`` no existe como clase aparte: un campo sin
    columna **es** un ``Field`` con ``store=False``, así que responde a los
    mismos atributos que cualquier otro. Aquí la jerarquía del stack los
    separa —``NonStored`` no desciende de ``models.Field``—, y el bucle de
    ``_FIELD_CLASS_ATTRIBUTES`` sólo alcanzaba a la clase de Django.

    Qué haría fallar a cada control
    --------------------------------

    ``test_it_answers_whether_it_is_searchable``
        CONTROL del hueco medido: antes levantaba ``AttributeError``. Su
        consumidor real es ``_field_setup_related``, que recorre la cadena
        preguntando ``f._description_searchable`` a cada eslabón — y un
        eslabón sin columna cortaba el montaje.

    ``test_it_is_not_stored``
        CONTROL del único defecto que NO se hereda tal cual: ``store`` vale
        ``True`` en ``Field`` y ``False`` aquí, que es lo que la clase
        significa. Instalar el defecto de ``Field`` a secas lo pondría en
        ``True`` y ``_description_searchable`` daría ``True`` para todos.
    """

    def test_it_answers_whether_it_is_searchable(self):
        assert NonStored(default=None, search='_x')._description_searchable
        assert not NonStored(default=None)._description_searchable

    def test_it_is_not_stored(self):
        assert NonStored(default=None).store is False

    def test_it_answers_the_rest_of_the_class_contract(self):
        """El resto de los atributos de clase, con el defecto de la fuente."""
        field = NonStored(default=None)
        faltantes = [name for name in _FIELD_CLASS_ATTRIBUTES
                     if not hasattr(field, name)]
        assert faltantes == [], (
            f'el campo sin columna no responde a {len(faltantes)} atributos '
            f'que la fuente declara en Field: {faltantes}')

    def test_the_related_chain_can_cross_it(self):
        """El consumidor real: ``_field_setup_related`` recorre la cadena.

        Qué lo haría fallar: que un eslabón sin columna no responda
        ``_description_searchable``. Era un ``AttributeError`` en el montaje,
        no un rechazo declarado.
        """
        eslabones = [NonStored(default=None, search='_x'),
                     NonStored(default=None)]
        assert [f._description_searchable for f in eslabones] == [True, False]
