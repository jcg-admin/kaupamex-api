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


import itertools

import pytest
from django.db import models
from django.test.utils import isolate_apps

from orm.domains import Domain, to_q
from orm.fields import _FIELD_CLASS_ATTRIBUTES, determine
import fields

from addons.base.models.ir_config_parameter import SystemParameter

pytestmark = pytest.mark.django_db


@pytest.fixture
def config_parameter():
    return SystemParameter


_HOLDERS = itertools.count()


def _column_less(**kwargs):
    """Un campo sin columna: el ``store=False`` de la fuente, que aquí es un
    campo de Django contribuido sin columna (TASK-API-0417, TASK-API-0418).

    Se contribuye a un modelo aislado porque ahí recibe sus atributos de la
    fuente —``search``, ``store``—, como en el ``_setup_attrs__`` de allá; el
    ``isolate_apps`` evita registrarlo y crear tablas.
    """
    field = fields.Char(store=False, **kwargs)
    with isolate_apps():
        meta = type('Meta', (), {'app_label': 'base'})
        type(f'SearchHolder{next(_HOLDERS)}', (models.Model,), {
            '__module__': __name__, 'Meta': meta, 'probe': field})
    return field


class _Recordset:
    """Sustituto mínimo de un recordset para ejercitar ``determine``."""

    def method_by_name(self, *args):
        return ('por-nombre', args)


class TestDetermine:
    """
    ``determine`` — el invocable o el nombre de método, ≙ ``fields.py:66``.
    """

    def test_resolves_a_method_given_by_name(self):
        records = _Recordset()
        assert determine('method_by_name', records, 'a', 'b') == (
            'por-nombre',
            ('a', 'b'),
        )

    def test_resolves_a_plain_callable_passing_the_records(self):
        def searcher(records, operator, value):
            return ('invocable', records, operator, value)

        records = _Recordset()
        assert determine(searcher, records, 'in', [1]) == (
            'invocable',
            records,
            'in',
            [1],
        )

    def test_rejects_something_that_is_neither(self):
        with pytest.raises(TypeError):
            determine(42, _Recordset())


class TestColumnLessSearch:
    """
    Un campo sin columna acepta ``search=`` y lo expone como el de la fuente.
    """

    def test_the_field_keeps_the_search_method(self):
        field = _column_less(search='_buscar')
        assert field.search == '_buscar'

    def test_without_search_the_attribute_is_none(self):
        assert _column_less().search is None

    def test_determine_domain_delegates_to_the_search_method(
        self, config_parameter
    ):
        field = _column_less(
            search=lambda records, operator, value: Domain(
                'key', operator, value
            ),
        )
        result = field.determine_domain(config_parameter, 'ilike', 'x')
        assert result == Domain('key', 'ilike', 'x')

    def test_determine_domain_without_search_is_not_implemented(
        self, config_parameter
    ):
        assert (
            _column_less().determine_domain(
                config_parameter, 'ilike', 'x'
            )
            is NotImplemented
        )


class TestFieldResolutionReachesTheColumnLessField:
    """``_field`` encuentra también el campo sin columna.

    La fuente guarda campos con y sin columna en el mismo ``_fields``; aquí
    los sin columna viven en ``_meta.private_fields`` y el registro del modelo
    los une a los demás.
    """

    def test_a_stored_field_still_resolves_through_meta(
        self, config_parameter
    ):
        condition = Domain('key', '=', 'x')
        assert condition._field(config_parameter) is not None

    def test_the_non_stored_display_name_resolves(self, config_parameter):
        condition = Domain('display_name', 'ilike', 'x')
        field = condition._field(config_parameter)
        assert field.store is False
        assert field.search is not None

    def test_a_name_that_is_neither_still_raises(self, config_parameter):
        with pytest.raises(ValueError):
            Domain('no_existe_en_ninguna_parte', '=', 1)._field(
                config_parameter
            )


class TestSearchDisplayNameReturnsADomain:
    """``_search_display_name`` devuelve un ``Domain``, no un ``QuerySet``.

    ≙ ``odoo19c: odoo/orm/models.py:1442``. La forma importa: un dominio se
    compone dentro de un ``any`` y un ``QuerySet`` no.
    """

    def test_the_result_is_a_domain(self, config_parameter):
        assert isinstance(
            config_parameter._search_display_name('ilike', 'x'), Domain
        )

    def test_it_searches_over_the_rec_name(self, config_parameter):
        """La fuente añade la condición dos veces: la rama ``like`` y, al
        final, ``convert_to_write`` del valor entero, que con un texto no
        falla. Su ``Domain.OR`` no reduce la repetida al construir; medido
        con el ``Domain`` de ``odoo19c``: ``['|', c, c]``. La reducción
        llega al buscar, no aquí."""
        condition = Domain('key', 'ilike', 'x')
        assert config_parameter._search_display_name('ilike', 'x') == (
            Domain.OR([condition, condition])
        )

    def test_the_empty_like_short_circuit_is_kept(self, config_parameter):
        assert (
            config_parameter._search_display_name('ilike', '') is Domain.TRUE
        )

    def test_the_domain_still_compiles_to_a_queryset(self, config_parameter):
        config_parameter.objects.create(key='una.clave', value='v')
        domain = config_parameter._search_display_name('ilike', 'una.cl')
        found = config_parameter.objects.filter(to_q(domain, config_parameter))
        assert [p.key for p in found] == ['una.clave']


class TestTheConditionIsReplacedBySearch:
    """El consumidor real: la condición se sustituye por el dominio buscado."""

    def test_a_condition_on_display_name_becomes_the_search_domain(
        self, config_parameter
    ):
        # La sustitución ocurre en el nivel FULL, como en la fuente
        # (``odoo19c: odoo/orm/domains.py:946-967``); ``optimize()`` (BASIC)
        # conserva la condición sobre ``display_name``.
        optimizado = Domain('display_name', 'ilike', 'abc').optimize_full(
            config_parameter
        )
        assert optimizado == Domain('key', 'ilike', 'abc').optimize_full(
            config_parameter
        )

    def test_the_replacement_composes_inside_a_conjunction(
        self, config_parameter
    ):
        combined = (
            Domain('display_name', 'ilike', 'abc') & Domain('value', '=', 'v')
        ).optimize_full(config_parameter)
        expected = (
            Domain('key', 'ilike', 'abc') & Domain('value', '=', 'v')
        ).optimize_full(config_parameter)
        assert combined == expected

    def test_the_replaced_condition_reaches_the_database(
        self, config_parameter
    ):
        config_parameter.objects.create(key='alfa.uno', value='1')
        config_parameter.objects.create(key='beta.dos', value='2')
        found = config_parameter.objects.filter(
            to_q(Domain('display_name', 'ilike', 'alfa'), config_parameter)
        )
        assert [p.key for p in found] == ['alfa.uno']

    def test_a_stored_field_is_left_alone(self, config_parameter):
        condition = Domain('key', 'ilike', 'abc')
        assert condition.optimize(config_parameter) == condition.optimize(
            config_parameter
        )
        assert 'key' in repr(condition.optimize(config_parameter))


class TestTheFallbackLadder:
    """Las tres ramas de respaldo de ``_optimize_field_search_method``."""

    def test_a_negative_operator_retries_with_the_positive_and_negates(
        self, config_parameter
    ):
        negative = Domain('display_name', 'not ilike', 'abc').optimize_full(
            config_parameter
        )
        positive = Domain('key', 'ilike', 'abc').optimize_full(
            config_parameter)
        assert negative == (~positive).optimize_full(config_parameter)

    def test_a_search_that_only_knows_equality_is_decomposed_for_in(
        self, config_parameter, monkeypatch
    ):
        def only_equality(records, operator, value):
            if operator != '=':
                return NotImplemented
            return Domain('key', '=', value)

        descriptor = Domain('display_name', '=', 'x')._field(config_parameter)
        monkeypatch.setattr(descriptor, 'search', only_equality)
        result = Domain(
            'display_name', 'in', ['a', 'b']
        )._optimize_field_search_method(config_parameter)
        assert result == Domain.OR(
            [Domain('key', '=', 'a'), Domain('key', '=', 'b')]
        )

    def test_a_search_that_supports_nothing_raises_naming_the_field(
        self, config_parameter, monkeypatch
    ):
        descriptor = Domain('display_name', '=', 'x')._field(config_parameter)
        monkeypatch.setattr(
            descriptor, 'search', lambda *_args: NotImplemented
        )
        with pytest.raises(ValueError, match='display_name'):
            Domain('display_name', 'ilike', 'x')._optimize_field_search_method(
                config_parameter
            )


class TestTheColumnLessFieldAnswersTheFieldContract:
    """Un campo sin columna responde al contrato de campo — ≙ ``Field``.

    En la fuente un campo sin columna **es** un ``Field`` con ``store=False``,
    así que responde a los mismos atributos que cualquier otro. Aquí también:
    es un campo de Django, y el bucle de ``_FIELD_CLASS_ATTRIBUTES`` lo
    alcanza como a cualquier otro.

    Qué haría fallar a cada control
    --------------------------------

    ``test_it_answers_whether_it_is_searchable``
        Su consumidor real es ``_field_setup_related``, que recorre la cadena
        preguntando ``f._description_searchable`` a cada eslabón.

    ``test_it_is_not_stored``
        ``store`` vale ``True`` en ``Field``; si el ``store=False`` declarado
        no llegara al campo, ``_description_searchable`` daría ``True`` para
        todos.
    """

    def test_it_answers_whether_it_is_searchable(self):
        assert _column_less(search='_x')._description_searchable
        assert not _column_less()._description_searchable

    def test_it_is_not_stored(self):
        assert _column_less().store is False

    def test_it_answers_the_rest_of_the_class_contract(self):
        """El resto de los atributos de clase, con el defecto de la fuente."""
        field = _column_less()
        missing = [
            name
            for name in _FIELD_CLASS_ATTRIBUTES
            if not hasattr(field, name)
        ]
        assert missing == [], (
            f'el campo sin columna no responde a {len(missing)} atributos '
            f'que la fuente declara en Field: {missing}'
        )

    def test_the_related_chain_can_cross_it(self):
        """El consumidor real: ``_field_setup_related`` recorre la cadena."""
        links = [_column_less(search='_x'), _column_less()]
        assert [f._description_searchable for f in links] == [True, False]
