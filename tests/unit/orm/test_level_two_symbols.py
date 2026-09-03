"""#330 — los tres símbolos sueltos de nivel 2 de ``odoo/orm/``.

Tras #328, ``scripts/orden_de_porte.py`` deja el nivel 2 con 22 símbolos: 15
ya se declaraban aquí, siete forman el ciclo duro que la tarea **#211** ataca
—``BaseModel``, ``BaseString``, ``Char``, ``Field``, ``Id``, ``MetaModel``,
``Registry``— y tres estaban sueltos y sin contraparte:

============================== ============================== =====================
Símbolo                        En la referencia                Aquí
============================== ============================== =====================
``depends_context``            ``decorators.py:273-296``      ``orm/decorators.py``
``ondelete``                   ``decorators.py:130-186``      ``orm/decorators.py``
``raise_on_invalid_object_name``  ``models.py:139-142``       ``orm/models.py``
============================== ============================== =====================

Y con ellos, la mitad que faltaba de sus tres hermanos ya presentes
============================================================================

Al abrir ``orm/decorators.py`` se midió que ``depends``, ``constrains`` y
``onchange`` estaban portados **a medias**: los tres escribían su marcador con
un cierre propio en vez de :func:`~orm.decorators.attrsetter`, y a los dos
primeros les faltaba la forma de **un solo argumento invocable** que la fuente
admite (``decorators.py:268-269`` y ``:126-127``); a ``depends``, además, la
guarda que rechaza depender del campo ``id`` (``:270``).

La forma invocable no es decorativa: obliga a que el lector la resuelva. La
fuente lo hace en ``odoo19c: odoo/orm/fields.py:595`` —``deps(model) if
callable(deps) else deps``— y aquí el lector es
:class:`~orm.registry._DerivedCollector`, que hacía ``tuple(declared)`` y
reventaba. Se le enseña lo mismo.

Los controles que discriminan
==============================

- ``ondelete`` es **keyword-only**: pasarle el valor por posición tiene que
  fallar. Sin el ``*`` de la firma, ``ondelete(False)`` pasaría y el marcador
  quedaría igual — el caso lo mide.
- ``depends`` con ``'id'`` **rechaza**, y también dentro de una cadena punteada
  (``'partner_id.id'``): el reparto por ``split('.')`` es lo que separa el caso
  que rechaza del que no.
- El colector **llama** al invocable con su modelo; el caso mide que le llega
  el modelo, no que devuelva algo.
"""
import inspect

import pytest

import orm.decorators as decorators
from orm import registry
from orm.decorators import (attrsetter, constrains, depends, depends_context,
                            onchange, ondelete)
from orm.models import raise_on_invalid_object_name


class TestDependsContextMarksTheContextKeys:
    """≙ ``depends_context`` (``odoo19c: odoo/orm/decorators.py:273-296``)."""

    def test_it_stores_the_keys_and_returns_the_method(self):
        @depends_context('company', 'pricelist')
        def method(self):
            pass
        assert method._depends_context == ('company', 'pricelist')

    def test_it_returns_the_same_object_so_it_composes(self):
        def method(self):
            pass
        assert depends_context('company')(method) is method

    def test_without_keys_it_stores_the_empty_tuple(self):
        @depends_context()
        def method(self):
            pass
        assert method._depends_context == ()

    def test_the_reader_of_this_marker_already_exists(self):
        """``Binary`` lo declara y el colector del registro lo lee — no es un
        marcador sin consumidor."""
        assert registry.field_depends_context.marker == '_depends_context'


class TestOndeleteMarksTheUnlinkPolicy:
    """≙ ``ondelete`` (``odoo19c: odoo/orm/decorators.py:130-186``)."""

    def test_it_stores_the_flag_and_returns_the_method(self):
        @ondelete(at_uninstall=False)
        def _unlink_if_user_inactive(self):
            pass
        assert _unlink_if_user_inactive._ondelete is False

    def test_it_stores_true_when_the_check_survives_uninstall(self):
        @ondelete(at_uninstall=True)
        def _unlink_except_default_lang(self):
            pass
        assert _unlink_except_default_lang._ondelete is True

    def test_the_flag_is_keyword_only(self):
        """EL CONTROL: la fuente escribe ``def ondelete(*, at_uninstall)``.
        Sin ese ``*``, pasarlo por posición pasaría y el marcador quedaría
        idéntico — el caso no distinguiría las dos firmas."""
        with pytest.raises(TypeError):
            ondelete(False)

    def test_it_is_required(self):
        with pytest.raises(TypeError):
            ondelete()


class TestRaiseOnInvalidObjectNameRefusesTheBadName:
    """≙ ``raise_on_invalid_object_name`` (``models.py:139-142``)."""

    def test_a_valid_name_passes_silently(self):
        assert raise_on_invalid_object_name('res.partner') is None

    def test_an_uppercase_name_is_refused(self):
        with pytest.raises(ValueError, match='_name attribute'):
            raise_on_invalid_object_name('Res.Partner')

    def test_a_name_with_a_dash_is_refused(self):
        with pytest.raises(ValueError):
            raise_on_invalid_object_name('res-partner')

    def test_the_message_names_the_offender(self):
        with pytest.raises(ValueError) as failure:
            raise_on_invalid_object_name('MAL')
        assert 'MAL' in str(failure.value)


class TestTheThreeSiblingsGainTheirMissingHalf:
    """``depends``, ``constrains`` y ``onchange`` — la mitad que faltaba."""

    def test_depends_stores_the_field_names(self):
        @depends('partner_id.name', 'partner_id.is_company')
        def _compute_pname(self):
            pass
        assert _compute_pname._depends == ('partner_id.name',
                                           'partner_id.is_company')

    def test_depends_accepts_a_single_callable(self):
        """``:268-269`` — «One may also pass a single function as argument»."""
        def dependencies(model):
            return ['name']

        @depends(dependencies)
        def _compute_pname(self):
            pass
        assert _compute_pname._depends is dependencies

    def test_depends_refuses_the_id_field(self):
        with pytest.raises(NotImplementedError, match="depend on field 'id'"):
            depends('id')

    def test_depends_refuses_id_inside_a_dotted_chain(self):
        """EL CONTROL del reparto: la guarda parte por ``.``, así que
        ``partner_id.id`` cae y ``partner_id`` no. Sin el ``split``, un
        ``'id' in arg`` rechazaría también ``partner_id``."""
        with pytest.raises(NotImplementedError):
            depends('partner_id.id')
        assert depends('partner_id') is not None

    def test_constrains_accepts_a_single_callable(self):
        def fields_of(model):
            return ['name']

        @constrains(fields_of)
        def _check_name(self):
            pass
        assert _check_name._constrains is fields_of

    def test_constrains_stores_the_field_names(self):
        @constrains('name', 'description')
        def _check_name(self):
            pass
        assert _check_name._constrains == ('name', 'description')

    def test_onchange_stores_the_field_names(self):
        @onchange('partner_id')
        def _onchange_partner(self):
            pass
        assert _onchange_partner._onchange == ('partner_id',)

    def test_the_five_decorators_go_through_attrsetter(self):
        """Ninguno reescribe el ``setattr``: una sola fuente para la regla,
        que es lo que ``calibration-verified-numbers.md`` pide."""
        for name in ('depends', 'constrains', 'onchange', 'depends_context',
                     'ondelete'):
            source = inspect.getsource(getattr(decorators, name))
            assert 'attrsetter(' in source, name
            assert 'setattr(' not in source, name


@pytest.mark.django_db
class TestTheCollectorResolvesTheCallableForm:
    """El lector de ``_depends``, ≙ ``odoo19c: odoo/orm/fields.py:595``."""

    def test_it_calls_the_callable_with_its_model(self):
        seen = []

        def dependencies(model):
            seen.append(model)
            return ['name']

        collector = registry._DerivedCollector('_depends')
        partner = registry.MODELS_BY_NAME['res.partner']
        assert collector._resolve(dependencies, partner) == ('name',)
        assert seen == [partner]

    def test_a_plain_sequence_comes_through_as_a_tuple(self):
        collector = registry._DerivedCollector('_depends')
        partner = registry.MODELS_BY_NAME['res.partner']
        assert collector._resolve(['a', 'b'], partner) == ('a', 'b')

    def test_the_real_table_still_builds(self):
        """El control positivo: el colector recorre TODO el registro, así que
        una resolución rota se ve aquí y no en un doble."""
        assert isinstance(registry.field_depends._build(), dict)
