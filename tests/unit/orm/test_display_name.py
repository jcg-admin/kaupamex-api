"""``display_name`` universal — la etiqueta en todo modelo, y su bloque.

≙ que ``display_name`` y sus cuatro compañeros cuelguen de ``BaseModel``
(``odoo19c: odoo/orm/models.py:473,1425-1543``): allá **todo** modelo los tiene
sin declarar nada.

Las dos vías, y por qué son dos
===============================

La base común (``TimeStampedModel``) cubre 285 de los 375 modelos concretos
nuestros — medido, no supuesto. Los 90 restantes los recibe de
``orm.model_classes.adopt_display_name`` sobre ``class_prepared``, la misma
pareja de vías que ``H-API-577`` estableció para el registro por nombre.

Tres divergencias de FORMA, heredadas del árbol y declaradas
=============================================================

El mixin las adopta porque cinco modelos ya las ejercían antes de existir:
``_compute_display_name`` **devuelve** la etiqueta (la fuente la asigna),
``_search_display_name`` devuelve un ``QuerySet`` (la fuente, un ``Domain``), y
``name_create``/``name_search`` son ``classmethod`` (la fuente usa
``@api.model``). Un default que no las respetara rompería a esos cinco.

Qué haría fallar a estos casos
==============================

Que un modelo declarara ``display_name`` como ``property`` en vez de dejar el
campo — que es exactamente lo que hacían once modelos antes de la tarea #134, y
lo que el segundo eje del gate mide. Ese es el modo de fallo real, y tiene su
caso: se rebasa un modelo a ``property`` y se comprueba que el gate lo
**nombra**. Un caso que sólo afirmara *"todos lo tienen"* no distinguiría un
gate que funciona de uno que devuelve la lista vacía siempre.
"""

import pytest

from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from addons.base.models import ResPartner
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.purchase_requisition.models import PurchaseOrderGroup
from orm.fields_nonstored import NonStored
from orm.model_classes import (DISPLAY_NAME_SYMBOLS,
                               THIRD_PARTY_MODULE_PREFIXES,
                               adopt_display_name, ensure_display_names)
from orm.models import DisplayNameMixin
from scripts import check_display_name
from scripts.check_display_name import not_a_field, offenders


def _ours():
    return [m for m in apps.get_models()
            if not m._meta.abstract and not m._meta.proxy
            and not m.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)]


class TestUniversalAdoption:
    """Todo modelo nuestro tiene la etiqueta y su bloque de cuatro."""

    def test_no_model_of_ours_is_left_out(self):
        assert offenders() == []

    def test_none_declares_it_as_something_other_than_the_field(self):
        assert not_a_field() == []

    def test_a_model_with_the_shared_base_got_it_by_inheritance(self):
        """``ResPartner`` lo hereda de ``TimeStampedModel``, no del adoptador."""
        assert issubclass(ResPartner, DisplayNameMixin)

    def test_the_five_forms_are_reachable(self):
        """Las cinco de la fuente, no una muestra."""
        for form in DISPLAY_NAME_SYMBOLS:
            assert getattr(SystemParameter, form, None) is not None, form

    def test_third_party_models_are_left_alone(self):
        """La exclusión declarada: no se toca lo que no es nuestro.

        Es la otra mitad del control. Sin ella el barrido podría estar
        adoptando **todo**, incluidos los de Django, y el caso de arriba
        pasaría igual sin decir nada de nuestro criterio.
        """
        assert 'display_name' not in vars(ContentType)
        assert not issubclass(ContentType, DisplayNameMixin)


class TestTheFieldAdmitsAssignment:
    """``display_name`` es campo, no ``property``: se lee Y se asigna.

    La fuente lo declara campo, y sus overrides **le asignan**
    (``lot.display_name = name``, ``odoo19c:
    product_expiry/models/production_lot.py:35``). Con una ``property`` de sólo
    lectura ese idioma revienta, y por eso el mecanismo es ``NonStored``.
    """

    def test_the_descriptor_is_the_one_of_the_mixin(self):
        assert isinstance(vars(DisplayNameMixin)['display_name'], NonStored)

    @pytest.mark.django_db
    def test_it_reads_the_computed_value(self):
        parametro = SystemParameter.objects.create(key='clave.uno', value='x')
        assert parametro.display_name == 'clave.uno'

    @pytest.mark.django_db
    def test_it_admits_assignment_and_the_assigned_value_wins(self):
        parametro = SystemParameter.objects.create(key='clave.dos', value='x')
        parametro.display_name = 'lo que la vista puso'
        assert parametro.display_name == 'lo que la vista puso'

    @pytest.mark.django_db
    def test_deleting_it_falls_back_to_the_computed_value(self):
        parametro = SystemParameter.objects.create(key='clave.tres', value='x')
        parametro.display_name = 'temporal'
        del parametro.display_name
        assert parametro.display_name == 'clave.tres'


class TestTheComputeFallsBackToTheDottedName:
    """Sin ``_rec_name``, la etiqueta es ``<modelo>,<id>`` — como la fuente.

    ``odoo19c: odoo/orm/models.py:1436-1439`` — ``f"{record._name},{record.id}"``
    cuando no hay campo que etiquete.
    """

    @pytest.mark.django_db
    def test_a_model_without_rec_name_gets_the_dotted_form(self):
        """``purchase.order.group`` no declara ``_rec_name``: no hay campo que
        etiquete una agrupación, y la fuente cae al nombre con punto."""
        grupo = PurchaseOrderGroup.objects.create()
        assert grupo.display_name == f'purchase.order.group,{grupo.pk}'

class TestAdoptDisplayNameDiscriminates:
    """El adoptador dice que NO en los tres casos en que debe decirlo."""

    def test_it_refuses_an_abstract_model(self):
        assert adopt_display_name(TimeStampedModel) == 0

    def test_it_refuses_a_third_party_model(self):
        assert adopt_display_name(ContentType) == 0

    def test_it_refuses_one_it_already_has(self):
        """Idempotente: el barrido corre en cada arranque."""
        assert adopt_display_name(SystemParameter) == 0

    def test_the_sweep_reports_how_many_it_installed(self):
        """No devuelve ``None``: devuelve el conteo, para poder medir.

        Con todo ya adoptado el conteo es 0, y ese 0 **es el resultado**: dice
        que el barrido es idempotente, no que no hiciera nada.
        """
        assert ensure_display_names() == 0


class TestTheGateDiscriminates:
    """El gate encuentra al que se sale — probado contra el defecto real.

    Sin este control el gate podría devolver la lista vacía siempre y los dos
    casos de ``TestUniversalAdoption`` pasarían igual: es el sub-patrón D de
    ``metrica-decide-la-conclusion.md``, el verde que no discrimina.
    """

    def test_it_names_a_model_that_declares_display_name_as_a_property(self):
        """El defecto que la tarea #134 corrigió en once modelos."""
        guardado = vars(SystemParameter).get('display_name')
        try:
            SystemParameter.display_name = property(
                lambda self: self._compute_display_name())
            fuera = not_a_field()
            assert any('base.SystemParameter.display_name' in line
                       for line in fuera), fuera
        finally:
            if guardado is None:
                del SystemParameter.display_name
            else:
                SystemParameter.display_name = guardado
        assert not_a_field() == []
        assert offenders() == []

    def test_it_names_a_model_missing_one_of_the_five(self):
        """Falta uno solo de los cinco y el gate lo nombra."""
        guardado = vars(SystemParameter).get('name_search')
        try:
            SystemParameter.name_search = None
            fuera = offenders()
            assert any('base.SystemParameter' in line and 'name_search' in line
                       for line in fuera), fuera
        finally:
            if guardado is None:
                del SystemParameter.name_search
            else:
                SystemParameter.name_search = guardado
        assert offenders() == []


class TestPrefixesStayInSync:
    """El gate y el adoptador miden el mismo conjunto.

    Si divergieran, el barrido adoptaría uno y el gate mediría otro — y el
    gate publicaría un 0 sobre una población distinta de la adoptada.
    """

    def test_the_gate_and_the_adopter_share_the_prefixes(self):
        assert (check_display_name.THIRD_PARTY_MODULE_PREFIXES
                == THIRD_PARTY_MODULE_PREFIXES)
