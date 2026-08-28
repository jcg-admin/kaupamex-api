"""El historial de código de ``ir.actions.server`` (#117).

≙ ``odoo19c: addons/base/models/ir_actions.py:464-539`` (el asistente y el
modelo de historial), ``:722-737`` (``create``), ``:739-742`` (``write``),
``:788-796`` (``_compute_show_code_history``) y ``:1236-1245``
(``history_wizard_action``).

Qué haría fallar a estos casos
==============================

Guardar dos veces el **mismo** código no debe crear una revisión: sin esa
guarda el historial crece en cada guardado y el asistente compararía un texto
consigo mismo. El caso de la escritura repetida es el que la mide.

``show_code_history`` sólo es cierto cuando existe una revisión **distinta**
de la vigente. Un caso que sólo contase filas pasaría con la comparación
ausente, así que hay uno que guarda el mismo código dos veces y afirma falso.
"""
import pytest

from addons.base.models.ir_actions import (
    IrActionsServer, IrActionsServerHistory, ServerActionHistoryWizard)
from orm.environments import context_scope


def _action(**kwargs):
    kwargs.setdefault('name', 'Accion')
    kwargs.setdefault('state', 'code')
    return IrActionsServer.objects.create(**kwargs)


@pytest.mark.django_db
class TestTheFirstRevisionIsBornWithTheAction:
    """≙ ``create``: la creación con código deja su primera entrada."""

    def test_creating_with_code_records_it(self):
        action = _action(code='x = 1\n')

        assert list(action.code_history.values_list('code', flat=True)) == \
            ['x = 1\n']

    def test_creating_without_code_records_nothing(self):
        assert _action(state='multi').code_history.count() == 0


@pytest.mark.django_db
class TestEachChangeOfCodeAddsARevision:
    """≙ ``write``: sólo cuando el código **cambia**."""

    def test_a_new_code_is_recorded(self):
        action = _action(code='x = 1\n')
        action.code = 'x = 2\n'
        action.save()

        assert action.code_history.count() == 2

    def test_writing_the_same_code_again_records_nothing(self):
        """El control que discrimina: sin la comparacion, esto daria 2."""
        action = _action(code='x = 1\n')
        action.save()

        assert action.code_history.count() == 1

    def test_the_newest_revision_comes_first(self):
        action = _action(code='x = 1\n')
        action.code = 'x = 2\n'
        action.save()

        assert action.code_history.first().code == 'x = 2\n'


@pytest.mark.django_db
class TestWhetherTheFormOffersTheHistory:
    """≙ ``_compute_show_code_history``."""

    def test_an_action_with_an_older_code_offers_it(self):
        action = _action(code='x = 1\n')
        action.code = 'x = 2\n'
        action.save()

        assert action.show_code_history is True

    def test_an_action_whose_only_revision_is_the_current_one_does_not(self):
        assert _action(code='x = 1\n').show_code_history is False

    def test_an_action_that_is_not_code_never_offers_it(self):
        action = _action(state='multi')
        IrActionsServerHistory.objects.create(action=action, code='ajeno')

        assert action.show_code_history is False


@pytest.mark.django_db
class TestTheWizardIsOpenedOnTheAction:
    """≙ ``history_wizard_action``: la acción de ventana que abre el asistente."""

    def test_it_targets_the_wizard_model(self):
        opened = _action(code='x = 1\n').history_wizard_action()

        assert opened['res_model'] == 'server.action.history.wizard'

    def test_it_carries_the_action_in_the_context(self):
        action = _action(code='x = 1\n')

        assert action.history_wizard_action()['context'] == \
            {'default_action_id': action.pk}


@pytest.mark.django_db
class TestTheWizardComparesTheTwoTexts:
    """El asistente ya portado, medido contra el historial que ahora se graba."""

    def test_the_default_revision_is_the_last_one_that_differs(self):
        action = _action(code='x = 1\n')
        action.code = 'x = 2\n'
        action.save()

        with context_scope(default_action_id=action.pk):
            assert ServerActionHistoryWizard._default_revision().code == 'x = 1\n'

    def test_the_diff_names_both_columns(self):
        action = _action(code='x = 1\n')
        action.code = 'x = 2\n'
        action.save()
        with context_scope(default_action_id=action.pk):
            wizard = ServerActionHistoryWizard(
                action=action,
                revision=ServerActionHistoryWizard._default_revision())

        assert 'Código actual' in wizard.code_diff

    def test_restoring_brings_the_old_code_back(self):
        action = _action(code='x = 1\n')
        action.code = 'x = 2\n'
        action.save()
        with context_scope(default_action_id=action.pk):
            wizard = ServerActionHistoryWizard(
                action=action,
                revision=ServerActionHistoryWizard._default_revision())

        wizard.restore_revision()

        assert IrActionsServer.objects.get(pk=action.pk).code == 'x = 1\n'


@pytest.mark.django_db
class TestTheHistoryIsPruned:
    """≙ ``_gc_histories``: por encima del tope se conservan las más nuevas."""

    def test_nothing_is_pruned_below_the_cap(self):
        action = _action(code='x = 0\n')
        for n in range(1, 5):
            IrActionsServerHistory.objects.create(action=action, code=f'x = {n}\n')

        IrActionsServerHistory()._gc_histories()

        assert action.code_history.count() == 5

    def test_above_the_cap_only_the_newest_survive(self, monkeypatch):
        monkeypatch.setattr(
            IrActionsServerHistory, '_max_entries_per_action', 3)
        action = _action(code='x = 0\n')
        for n in range(1, 6):
            IrActionsServerHistory.objects.create(action=action, code=f'x = {n}\n')

        IrActionsServerHistory()._gc_histories()

        assert action.code_history.count() == 3
