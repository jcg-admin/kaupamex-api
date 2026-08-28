"""``AccessManager`` universal — las cuatro formas de permiso, en todo modelo.

≙ que ``check_access``, ``has_access``, ``_check_access`` y
``_filtered_access`` cuelguen de ``BaseModel``
(``odoo19c: odoo/orm/models.py:4100-4135``): allá **todo** modelo las tiene
sin declarar nada.

La divergencia de forma, declarada
==================================

Aquí las lleva un ``Manager``, porque ``models.Model`` es el de Django y no es
nuestro. La universalidad se recupera en ``class_prepared``, con el mismo par
de vías —señal más barrido— que ``H-API-577`` estableció para el registro por
nombre: la señal cubre lo que llega después de importar el módulo, el barrido
lo que ya estaba.

Qué haría fallar a estos casos
==============================

Que un modelo declarara manager propio sobre ``models.Manager`` en vez de
sobre ``AccessManager`` — que es exactamente lo que ``account.AccountTax``
hacía, y lo que el gate encontró al cablearse. Ese es el modo de fallo real, y
tiene su caso: se rebasa un modelo a ``models.Manager`` y se comprueba que el
gate lo **nombra**. Un caso que sólo afirmara *"todos lo tienen"* no
distinguiría un gate que funciona de uno que devuelve la lista vacía siempre.
"""

import pytest

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models

from addons.base.models import ResPartner
from addons.crm.models import ContactMessage
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_rule import RuleScopedManager
from addons.base.models.soft_delete_mixin import (AllObjectsManager,
                                                  SoftDeleteManager)
from addons.base.models.res_users import ResUsersManager
from orm.model_classes import (THIRD_PARTY_MODULE_PREFIXES,
                               adopt_access_manager, ensure_access_managers)
from orm.models import AccessManager, AccessQuerySet
from scripts import check_access_manager
from scripts.check_access_manager import offenders


def _concretos():
    return [m for m in apps.get_models() if not m._meta.abstract]


def _nuestros():
    return [m for m in _concretos()
            if not m.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)]


class TestUniversalAdoption:
    """Todo modelo nuestro resuelve el recordset con permiso."""

    def test_no_model_of_ours_is_left_out(self):
        assert offenders() == []

    def test_a_model_without_its_own_manager_got_it(self):
        """``SystemParameter`` no declara manager; lo puso la señal."""
        assert isinstance(SystemParameter._default_manager.get_queryset(),
                          AccessQuerySet)

    def test_a_model_with_the_shared_base_got_it_too(self):
        """``ResPartner`` lo hereda de ``TimeStampedModel``, no de la señal."""
        assert isinstance(ResPartner._default_manager.get_queryset(),
                          AccessQuerySet)

    def test_the_four_forms_are_reachable(self):
        """Las cuatro de la fuente, no una muestra."""
        qs = ResPartner.objects.all()
        for form in ('check_access', 'has_access', '_check_access',
                     '_filtered_access'):
            assert hasattr(qs, form), form

    def test_third_party_models_are_left_alone(self):
        """La exclusión declarada: no se toca lo que no es nuestro.

        Es la otra mitad del control. Sin ella el barrido podría estar
        adoptando **todo**, incluidos los de Django, y el caso de arriba
        pasaría igual sin decir nada de nuestro criterio.
        """
        assert not isinstance(ContentType._default_manager.get_queryset(),
                              AccessQuerySet)


class TestOwnManagersDeriveFromIt:
    """Un manager propio no esquiva las cuatro formas: deriva de ellas."""

    @pytest.mark.parametrize('manager_class', [
        SoftDeleteManager, AllObjectsManager, ResUsersManager,
        RuleScopedManager,
    ])
    def test_the_declared_managers_derive_from_access_manager(self,
                                                              manager_class):
        assert issubclass(manager_class, AccessManager)

    @pytest.mark.django_db
    def test_the_soft_delete_manager_still_hides_the_deleted(self):
        """Derivar no puede comerse lo que el manager ya hacía.

        **Este caso leía el código fuente** —``inspect.getsource`` sobre
        ``SoftDeleteManager.get_queryset``, buscando ``is_deleted=False``— y por
        eso pasó en verde mientras el árbol estaba roto: el filtro seguía
        escrito, y lo que se había perdido era **quién resuelve el manager**.
        Es el sub-patrón D de ``metrica-decide-la-conclusion.md`` en su forma
        más cara: el control no puede fallar por el defecto que dice medir.

        Ahora se borra una fila de verdad. Qué lo haría fallar: que ``objects``
        deje de resolver a ``SoftDeleteManager`` —por eclipse de MRO o por
        adopción indebida— o que su filtro se pierda.
        """
        mensaje = ContactMessage.objects.create(
            name='Control de eclipse',
            email='control@example.com',
            subject='Control',
            body='La fila se borra y no debe volver a verse.')
        pk = mensaje.pk
        mensaje.delete()
        assert not ContactMessage.objects.filter(pk=pk).exists()
        assert ContactMessage.all_objects.get(pk=pk).is_deleted is True

    def test_the_soft_delete_model_is_who_resolves_objects(self):
        """El manager que gana es el de la base especializada.

        Con ``objects = AccessManager()`` colgado de ``TimeStampedModel`` esto
        resolvía ``ManagerFromAccessQuerySet``: la base genérica está antes en
        el MRO y ``Options.managers`` se queda con el primero.
        """
        assert isinstance(ContactMessage._meta.managers_map['objects'],
                          SoftDeleteManager)


class TestAdoptAccessManagerDiscriminates:
    """El adoptador dice que NO en los cuatro casos en que debe decirlo."""

    def test_it_refuses_an_abstract_model(self):
        assert adopt_access_manager(TimeStampedModel) is False

    def test_it_refuses_a_third_party_model(self):
        assert adopt_access_manager(ContentType) is False

    def test_it_refuses_a_model_with_its_own_manager(self):
        """``ResUsers`` declara el suyo; el adoptador no lo pisa."""
        assert adopt_access_manager(ResUsers) is False

    def test_it_refuses_one_it_already_adopted(self):
        """Idempotente: el barrido corre en cada arranque."""
        assert adopt_access_manager(SystemParameter) is False

    def test_the_sweep_reports_how_many_it_adopted(self):
        """No devuelve ``None``: devuelve el conteo, para poder medir.

        Con todo ya adoptado el conteo es 0, y ese 0 **es el resultado**: dice
        que el barrido es idempotente, no que no hiciera nada.
        """
        assert ensure_access_managers() == 0


class TestTheGateDiscriminates:
    """El gate encuentra al que se sale — probado contra un caso real.

    Sin este control el gate podría devolver la lista vacía siempre y el caso
    ``test_no_model_of_ours_is_left_out`` pasaría igual: es el sub-patrón D de
    ``metrica-decide-la-conclusion.md``, el verde que no discrimina.
    """

    def test_it_names_a_model_rebased_to_a_plain_manager(self):
        anterior = SystemParameter._meta.local_managers
        try:
            SystemParameter._meta.local_managers = []
            SystemParameter._meta._expire_cache()
            SystemParameter.add_to_class('objects', django_models.Manager())
            assert 'base.SystemParameter' in offenders()
        finally:
            SystemParameter._meta.local_managers = anterior
            SystemParameter._meta._expire_cache()
        # Restaurado: el gate vuelve a estar limpio.
        assert offenders() == []


class TestNoDeclaredManagerIsShadowed:
    """El segundo eje del gate: ninguna base pierde su manager por el MRO.

    ``Options.managers`` recorre el MRO por profundidad y se queda con el
    **primer** manager de cada nombre. Un manager colgado de una base genérica
    eclipsa al de una especializada declarada más abajo, y —si el eclipsante
    también deriva de ``AccessManager``— el primer eje del gate sigue en verde.
    Medido: pasaba en **8** modelos y el gate publicaba OK.
    """

    def test_the_tree_has_none(self):
        assert check_access_manager.shadowed() == []

    def test_it_names_the_eclipse_when_a_generic_base_declares_objects(self):
        """El control se prueba contra el defecto real, no contra uno inventado.

        Se cuelga un ``objects`` de ``TimeStampedModel`` —el cambio exacto que
        rompió el árbol— y se comprueba que la función lo nombra en los modelos
        de borrado lógico. Sin este caso, ``shadowed() == []`` no distinguiría
        un eje que funciona de uno que devuelve la lista vacía siempre.
        """
        previos = list(TimeStampedModel._meta.local_managers)
        try:
            manager = AccessManager()
            manager.name = 'objects'
            manager.model = TimeStampedModel
            TimeStampedModel._meta.local_managers = [manager]
            for model in _nuestros():
                model._meta._expire_cache()
            eclipsados = check_access_manager.shadowed()
        finally:
            TimeStampedModel._meta.local_managers = previos
            for model in _nuestros():
                model._meta._expire_cache()

        assert any('crm.ContactMessage.objects' in line
                   and 'SoftDeleteManager' in line for line in eclipsados)
        assert check_access_manager.shadowed() == []


class TestPrefixesStayInSync:
    """El gate y el adoptador miden el mismo conjunto.

    Si divergieran, el barrido adoptaría uno y el gate mediría otro — y el
    gate publicaría un 0 sobre una población distinta de la adoptada.
    """

    def test_the_gate_and_the_adopter_share_the_prefixes(self):
        assert (check_access_manager.THIRD_PARTY_MODULE_PREFIXES
                == THIRD_PARTY_MODULE_PREFIXES)
