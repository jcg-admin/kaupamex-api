"""Actual PG schema controls for complete demo errors; not signal acceptance."""
from contextlib import contextmanager
import importlib

from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.state import ModelState, ProjectState
import pytest

from addons.base.models.ir_demo_failure import IrDemoFailure, IrDemoFailureWizard
from addons.base.models.ir_module import IrModule

pytestmark = pytest.mark.django_db(transaction=True)
LONG_ERROR = 'Traceback original\n' + 'detalle completo Ω\n' * 300


@contextmanager
def storage_models(legacy=False):
    assert connection.vendor == 'postgresql'
    state = ProjectState()
    for model in (IrModule, IrDemoFailureWizard, IrDemoFailure):
        item = ModelState.from_model(model)
        item.options['db_table'] = 'contract_demo_' + model._meta.model_name
        item.options['indexes'] = []
        item.options['constraints'] = []
        if model is IrDemoFailure and legacy:
            item.fields['error'].max_length = 255
        state.add_model(item)
    classes = [state.apps.get_model('base', model.__name__) for model in
               (IrModule, IrDemoFailureWizard, IrDemoFailure)]
    with connection.schema_editor() as editor:
        for model in classes:
            editor.create_model(model)
    try:
        yield state, classes
    finally:
        with connection.schema_editor() as editor:
            for model in reversed(classes):
                editor.delete_model(model)


def test_complete_error_round_trips_without_truncation():
    with storage_models() as (_, (module, wizard, failure)):
        row = module.objects.create(name='error_contract')
        saved = failure.objects.create(module_id=row.pk, error=LONG_ERROR)
        assert failure.objects.get(pk=saved.pk).error == LONG_ERROR


def test_error_migration_preserves_history_and_refuses_lossy_reverse():
    migration = importlib.import_module(
        'addons.base.migrations.0089_demo_failure_error_length'
    ).Migration('0089_demo_failure_error_length', 'base')
    with storage_models(legacy=True) as (state, (module, wizard, failure)):
        row = module.objects.create(name='historical_error')
        old = failure.objects.create(module_id=row.pk, error='original short error')
        with connection.schema_editor() as editor:
            after = migration.apply(state.clone(), editor)
        current = after.apps.get_model('base', 'IrDemoFailure')
        assert current.objects.get(pk=old.pk).error == 'original short error'
        long = current.objects.create(module_id=row.pk, error=LONG_ERROR)
        with pytest.raises(IrreversibleError, match='255'):
            with connection.schema_editor() as editor:
                migration.unapply(state.clone(), editor)
        assert current.objects.get(pk=long.pk).error == LONG_ERROR
        current.objects.filter(pk=long.pk).delete()
        with connection.schema_editor() as editor:
            migration.unapply(state.clone(), editor)
        assert failure.objects.get(pk=old.pk).error == 'original short error'
