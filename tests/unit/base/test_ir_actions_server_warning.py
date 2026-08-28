"""``warning`` y la mitad que ``_check_children`` consume (#116).

≙ ``odoo19c: addons/base/models/ir_actions.py:639`` (el campo),
``:744-757`` (``_warning_depends``), ``:761-799`` (``_get_warning_messages``),
``:804-810`` (``_compute_warning``) y ``:967-973`` (``_check_children``).

``_check_children`` tenía **una** de sus dos mitades: la del ciclo. La otra
—rechazar el guardado cuando alguna hija trae aviso— estaba declarada
bloqueada por ``warning``, que no existía. Este archivo mide las dos.

Qué haría fallar a estos casos
==============================

``warning`` es **recursivo**: una hija con aviso hace que su padre avise. Un
caso que sólo mirase el aviso propio pasaría con la recursión ausente, así que
hay un caso de dos niveles que la exige. Y el rechazo de ``_check_children`` se
mide **guardando**, no llamando al método: es su consumidor real.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models.ir_actions import IrActionsServer


def _action(**kwargs):
    kwargs.setdefault('name', 'Accion')
    kwargs.setdefault('state', 'multi')
    return IrActionsServer.objects.create(**kwargs)


@pytest.mark.django_db
class TestTheWarningIsSilentWhenNothingIsWrong:
    """Sin motivo, ``warning`` es falso — ``else: action.warning = False``."""

    def test_an_action_without_children_does_not_warn(self):
        assert _action().warning is False

    def test_a_child_with_the_same_model_does_not_warn(self):
        parent = _action(model_name='base.ResPartner')
        _action(model_name='base.ResPartner', parent=parent)

        assert parent.warning is False


@pytest.mark.django_db
class TestTheModelBranch:
    """≙ *"Following child actions should have the same model"*."""

    def test_a_child_with_another_model_warns(self):
        parent = _action(model_name='base.ResPartner')
        _action(name='Hija', model_name='base.ResCountry', parent=parent)

        assert 'Hija' in parent.warning

    def test_the_message_names_the_model_of_the_parent(self):
        parent = _action(model_name='base.ResPartner')
        _action(name='Hija', model_name='base.ResCountry', parent=parent)

        assert 'base.ResPartner' in parent.warning

    def test_a_parent_without_model_does_not_warn(self):
        """La guarda ``if self.model_id`` de la fuente: sin modelo no compara."""
        parent = _action()
        _action(name='Hija', model_name='base.ResCountry', parent=parent)

        assert parent.warning is False


@pytest.mark.django_db
class TestTheRecursiveBranch:
    """≙ *"Following child actions have warnings"* — ``recursive=True``."""

    def test_a_grandchild_warning_reaches_the_grandparent(self):
        """El caso que exige la recursión: sin ella el abuelo no se entera."""
        grandparent = _action(name='Abuela')
        parent = _action(name='Madre', model_name='base.ResPartner',
                         parent=grandparent)
        _action(name='Nieta', model_name='base.ResCountry', parent=parent)

        assert 'Madre' in grandparent.warning

    def test_the_cycle_guard_stops_the_recursion(self):
        """Un ciclo no puede colgar el cómputo; lo corta el conjunto visto."""
        first = _action(name='Primera')
        second = _action(name='Segunda', parent=first)
        IrActionsServer.objects.filter(pk=first.pk).update(parent=second)

        assert first.__class__.objects.get(pk=first.pk).warning is not None


@pytest.mark.django_db
class TestCheckChildrenRefusesTheSave:
    """La mitad que faltaba: guardar con una hija en aviso se rechaza."""

    def test_saving_with_a_warning_child_is_refused(self):
        parent = _action(name='Madre', model_name='base.ResPartner')
        _action(name='Hija', model_name='base.ResCountry', parent=parent)
        nieta_parent = IrActionsServer.objects.get(pk=parent.pk)
        _action(name='Nieta', model_name='base.ResCountry',
                parent=nieta_parent)

        grandparent = _action(name='Abuela')
        IrActionsServer.objects.filter(pk=parent.pk).update(
            parent=grandparent)
        grandparent.name = 'Abuela editada'

        with pytest.raises(ValidationError, match='avisos'):
            grandparent.save()

    def test_saving_without_warning_children_is_allowed(self):
        parent = _action(name='Madre', model_name='base.ResPartner')
        _action(name='Hija', model_name='base.ResPartner', parent=parent)

        parent.name = 'Madre editada'
        parent.save()

        assert IrActionsServer.objects.get(pk=parent.pk).name == 'Madre editada'

    def test_the_cycle_half_still_refuses(self):
        """La mitad que ya existía no se pierde al añadir la segunda."""
        first = _action(name='Primera')
        second = _action(name='Segunda', parent=first)
        IrActionsServer.objects.filter(pk=first.pk).update(parent=second)

        reloaded = IrActionsServer.objects.get(pk=first.pk)
        with pytest.raises(ValidationError, match='Recursión'):
            reloaded.save()


@pytest.mark.django_db
class TestTheDependsIsDeclared:
    """``_warning_depends`` existe con los nombres de la fuente."""

    def test_it_lists_the_names_the_source_lists(self):
        declared = IrActionsServer._warning_depends()

        assert 'state' in declared
        assert 'child_ids.warning' in declared
