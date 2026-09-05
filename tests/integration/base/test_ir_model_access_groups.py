"""Tests — la expresión de grupos que concede un modo (``_get_access_groups``).

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py:2109-2126``
(``IrModelAccess._get_access_groups``) y ``base/models/res_groups.py:362-376``
(``ResGroups._get_group_definitions``), los dos portados por la tarea **#204**
junto con ``tools/set_expression.py``, que era su bloqueo.

Lo que la fuente decide, y es lo que estos casos fijan
======================================================

``_get_access_groups`` tiene **tres** desenlaces, y el orden importa:

1. ninguna ACL concede el modo → ``empty`` — nadie;
2. **alguna** ACL sin grupo → ``universe`` — todos, aunque haya además ACL por
   grupo, porque una fila global ya abrió el modo;
3. si no → ``from_ids`` de los grupos de las ACL que lo conceden.

Qué haría fallar a cada control
--------------------------------

``test_without_any_acl_the_expression_is_empty``
    El eje fail-closed. Lo haría fallar leer la ausencia de fila como permiso.

``test_a_global_row_opens_the_mode_to_everyone``
    El desenlace 2. Lo haría fallar mirar sólo ``group_id`` no nulo.

``test_a_global_row_wins_over_a_group_row``
    CONTROL de **orden**: con las dos clases de fila presentes, un puerto que
    evaluara ``from_ids`` antes que el caso global daría la expresión de grupo
    en vez de ``universe``. Los otros casos pasan igual con el orden invertido;
    éste no.

``test_a_row_for_another_mode_does_not_grant_this_one``
    CONTROL de discriminación por modo, hermano del de ``check``.

``test_the_expression_answers_membership_through_matches``
    Cierra el circuito: la expresión no es un dato, es la pregunta que
    ``web._has_access`` le hace con los grupos efectivos del usuario.

``test_an_implied_group_also_matches``
    CONTROL de la **clausura**: la ACL nombra al grupo padre y el usuario está
    sólo en el hijo. Lo haría fallar preguntar contra ``group_ids`` en vez de
    contra la clausura de ``_get_group_ids``.

Medido con la guarda anulada
-----------------------------

El grafo se memoriza en la familia ``groups``, así que su **invalidador** es
la guarda que estos casos tienen que poder ver. Ninguno lo purga por su cuenta:
un caso que se limpiara el memo mediría el álgebra y sería ciego al defecto que
la destapó (``KeyError`` al pedir la expresión de un grupo recién creado).

Sustituyendo el cuerpo de ``ResGroups.save``/``delete`` por su ``super()``
pelado —es decir, quitando ``registry.clear_cache('groups')``— la suite pasa
de **15 passed** a **4 failed, 11 passed**. Caen exactamente los cuatro cuyo
único invalidador es ése:

- ``test_a_group_row_yields_that_group``
- ``test_the_expression_answers_membership_through_matches``
- ``test_the_graph_carries_the_user_type_as_a_disjunction``
- ``test_a_group_without_external_id_falls_back_to_its_pk``

Los once que sobreviven **no** son un verde falso: o no consultan el grafo
(los que dan ``empty``/``universe``), o los cubre **otro** invalidador que esa
anulación no toca — el receptor de ``m2m_changed`` sobre ``implied_ids`` y el
``clear_cache`` de ``IrModelData._update_xmlids``, que también están portados.
"""
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.res_groups import ResGroups
from orm import registry

pytestmark = pytest.mark.integration

#: El mismo ancla que ``test_ir_model_access_check``: un modelo de ``base`` que
#: el sembrador de ACL no cubre, para medir el mecanismo y no la semilla.
MODEL_LABEL = 'base.ResDeviceLog'


def _acl(mode='read', group=None, active=True, name='acl de prueba'):
    """Declara una fila de ACL para ``MODEL_LABEL`` con un solo permiso."""
    row, _ = IrModel.objects.get_or_create(
        model=MODEL_LABEL, defaults={'name': 'Registro de dispositivo'})
    return IrModelAccess.objects.create(
        name=name, model_id=row, group_id=group, active=active,
        **{f'perm_{mode}': True})


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password='GruposPrueba123!')


class TestTheThreeOutcomes:
    """Los tres desenlaces de ``_get_access_groups``, en su orden."""

    def test_without_any_acl_the_expression_is_empty(self, db):
        groups = IrModelAccess._get_access_groups(MODEL_LABEL, 'read')
        assert groups.is_empty()
        assert not groups.matches([1, 2, 3])

    def test_a_global_row_opens_the_mode_to_everyone(self, db):
        _acl('read', group=None)
        groups = IrModelAccess._get_access_groups(MODEL_LABEL, 'read')
        assert groups.is_universal()

    def test_a_group_row_yields_that_group(self, db):
        group = ResGroups.objects.create(name='lectores de bitácora')
        _acl('read', group=group)
        groups = IrModelAccess._get_access_groups(MODEL_LABEL, 'read')
        assert not groups.is_empty()
        assert not groups.is_universal()
        assert groups.matches([group.pk])
        assert not groups.matches([group.pk + 1000])

    def test_a_global_row_wins_over_a_group_row(self, db):
        group = ResGroups.objects.create(name='lectores con fila propia')
        _acl('read', group=group, name='acl por grupo')
        _acl('read', group=None, name='acl global')
        groups = IrModelAccess._get_access_groups(MODEL_LABEL, 'read')
        assert groups.is_universal(), (
            'una ACL global abre el modo a todos aunque haya además una por '
            'grupo — es el orden que la fuente fija')

    def test_a_row_for_another_mode_does_not_grant_this_one(self, db):
        _acl('write', group=None)
        assert IrModelAccess._get_access_groups(MODEL_LABEL, 'read').is_empty()
        assert IrModelAccess._get_access_groups(MODEL_LABEL, 'write').is_universal()

    def test_an_inactive_row_grants_nothing(self, db):
        _acl('read', group=None, active=False)
        assert IrModelAccess._get_access_groups(MODEL_LABEL, 'read').is_empty()

    def test_an_invalid_mode_raises(self, db):
        with pytest.raises(ValueError):
            IrModelAccess._get_access_groups(MODEL_LABEL, 'browse')


class TestTheExpressionAnswersMembership:
    """La expresión se consume con ``matches``, no leyéndole los ids."""

    def test_the_expression_answers_membership_through_matches(self, db):
        group = ResGroups.objects.create(name='con acceso')
        _acl('read', group=group)
        inside = _user('grupos.dentro@kaupamex.mx')
        outside = _user('grupos.fuera@kaupamex.mx')
        inside.group_ids.add(group)
        registry.clear_cache('stable')

        groups = IrModelAccess._get_access_groups(MODEL_LABEL, 'read')
        assert groups.matches(inside._get_group_ids())
        assert not groups.matches(outside._get_group_ids())

    def test_an_implied_group_also_matches(self, db):
        parent = ResGroups.objects.create(name='padre con acceso')
        child = ResGroups.objects.create(name='hijo que lo implica')
        child.implied_ids.add(parent)
        _acl('read', group=parent)
        who = _user('grupos.implicado@kaupamex.mx')
        who.group_ids.add(child)
        registry.clear_cache('stable')

        groups = IrModelAccess._get_access_groups(MODEL_LABEL, 'read')
        assert parent.pk not in who.group_ids.values_list('pk', flat=True), (
            'el usuario NO está en el grupo que la ACL nombra — si lo '
            'estuviera, el caso no mediría la clausura')
        assert groups.matches(who._get_group_ids())


class TestTheGroupDefinitions:
    """≙ ``ResGroups._get_group_definitions`` — el constructor del grafo."""

    def test_the_graph_carries_the_implication_as_a_superset(self, db):
        parent = ResGroups.objects.create(name='conjunto mayor')
        child = ResGroups.objects.create(name='conjunto menor')
        child.implied_ids.add(parent)

        definitions = ResGroups._get_group_definitions()
        assert parent.pk in definitions.get_superset_ids([child.pk])
        assert child.pk in definitions.get_subset_ids([parent.pk])

    def test_the_graph_carries_the_user_type_as_a_disjunction(self, db):
        internal = ResGroups.objects.create(
            name='del tipo interno', user_type=ResGroups.USER_TYPE_INTERNAL)
        portal = ResGroups.objects.create(
            name='del tipo portal', user_type=ResGroups.USER_TYPE_PORTAL)

        definitions = ResGroups._get_group_definitions()
        assert portal.pk in definitions.get_disjoint_ids([internal.pk])
        # Y el control que discrimina: un grupo SIN tipo no es disjunto de
        # nadie, que es lo que ``ResGroups.disjoint_ids`` decide.
        plain = ResGroups.objects.create(name='sin tipo de usuario')
        assert ResGroups._get_group_definitions().get_disjoint_ids([plain.pk]) == []

    def test_a_group_without_external_id_falls_back_to_its_pk(self, db):
        plain = ResGroups.objects.create(name='sin identificador externo')
        definitions = ResGroups._get_group_definitions()
        assert definitions.get_id(str(plain.pk)) == plain.pk

    def test_a_seeded_group_is_addressed_by_its_external_id(self, db):
        data_model = apps.get_model('base', 'IrModelData')
        seeded = ResGroups.objects.create(name='con identificador externo')
        data_model.set_xmlid(seeded, 'base.group_de_prueba_204')

        definitions = ResGroups._get_group_definitions()
        assert definitions.get_id('base.group_de_prueba_204') == seeded.pk
        assert str(definitions.parse('base.group_de_prueba_204')) == (
            "'base.group_de_prueba_204'")


class TestHasGroupGoesThroughTheGraph:
    """``ResUsers._has_group`` resuelve el xmlid con ``get_id`` — ``:1094``."""

    def test_membership_by_external_id(self, db):
        data_model = apps.get_model('base', 'IrModelData')
        group = ResGroups.objects.create(name='grupo direccionable')
        data_model.set_xmlid(group, 'base.group_direccionable_204')
        who = _user('grupos.xmlid@kaupamex.mx')
        registry.clear_cache('stable')

        assert not who._has_group('base.group_direccionable_204')
        who.group_ids.add(group)
        registry.clear_cache('stable')
        assert who._has_group('base.group_direccionable_204')

    def test_an_unknown_external_id_is_false_not_an_error(self, db):
        who = _user('grupos.desconocido@kaupamex.mx')
        assert who._has_group('base.group_que_no_existe_204') is False
