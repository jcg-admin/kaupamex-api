"""Migración del catálogo con datos históricos y DDL PostgreSQL reales."""
from contextlib import contextmanager
from copy import deepcopy
import importlib

from django.db import connection, models
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.state import ModelState, ProjectState
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModule, IrModuleCategory


pytestmark = pytest.mark.django_db(transaction=True)


@contextmanager
def historical_category_tables():
    """Reutiliza ProjectState sin rebajar el esquema del runtime de pruebas."""
    assert connection.vendor == 'postgresql'
    state = ProjectState()
    source_models = (IrModuleCategory, IrModelData, IrModule)
    for model in source_models:
        item = ModelState.from_model(model)
        item.options['db_table'] = 'contract_category_' + model._meta.model_name
        item.options['constraints'] = []
        item.options['indexes'] = []
        if model is IrModule:
            item.fields.pop('category_path', None)
            item.fields['category'] = models.CharField(
                max_length=100, blank=True, default='Uncategorized',
            )
        state.add_model(item)
    historical_models = [state.apps.get_model('base', m.__name__) for m in source_models]
    with connection.schema_editor() as editor:
        for model in historical_models:
            editor.create_model(model)
    try:
        yield state, historical_models
    finally:
        with connection.schema_editor() as editor:
            for model in reversed(historical_models):
                editor.delete_model(model)


def _migration():
    migration = importlib.import_module(
        'addons.base.migrations.0090_module_category_tree',
    ).Migration('0090_module_category_tree', 'base')
    migration.operations = deepcopy(migration.operations)
    return migration


def test_category_migration_preserves_paths_identity_state_and_version():
    with historical_category_tables() as (state, (_, _, old_module)):
        original = old_module.objects.create(
            name='contract_category_module', category='Sales/Child',
            state='installed', version='19.0.2', installed_version='19.0.1',
        )
        blank = old_module.objects.create(name='contract_blank_module', category='')
        migration = _migration()
        with connection.schema_editor() as editor:
            after = migration.apply(state.clone(), editor)

        module = after.apps.get_model('base', 'IrModule')
        row = module.objects.get(pk=original.pk)
        assert row.category_path == 'Sales/Child'
        assert row.category.name == 'Child'
        assert row.category.parent.name == 'Sales'
        assert (row.state, row.version, row.installed_version) == (
            'installed', '19.0.2', '19.0.1',
        )
        assert module.objects.get(pk=blank.pk).category_path == ''
        assert module.objects.get(pk=blank.pk).category_id is None
        identity = after.apps.get_model('base', 'IrModelData').objects.get(
            module='base', name='module_category_sales_child',
        )
        assert (identity.model, identity.res_id, identity.noupdate) == (
            'base.IrModuleCategory', row.category_id, True,
        )

        with connection.schema_editor() as editor:
            migration.unapply(state.clone(), editor)
        old = old_module.objects.get(pk=original.pk)
        assert (old.category, old.state, old.installed_version) == (
            'Sales/Child', 'installed', '19.0.1',
        )
        assert old_module.objects.get(pk=blank.pk).category == ''


def test_category_migration_refuses_ambiguous_identity_without_data_loss():
    with historical_category_tables() as (state, (category, identity, module)):
        module.objects.create(name='contract_category_one', category='A B')
        module.objects.create(name='contract_category_two', category='A_B')

        with pytest.raises(RuntimeError, match='colisi'):
            with connection.schema_editor() as editor:
                _migration().apply(state.clone(), editor)

        assert set(module.objects.values_list('category', flat=True)) == {'A B', 'A_B'}
        assert category.objects.count() == 0
        assert identity.objects.count() == 0


def test_category_reverse_refuses_to_truncate_a_new_long_path():
    with historical_category_tables() as (state, (_, _, _)):
        migration = _migration()
        with connection.schema_editor() as editor:
            after = migration.apply(state.clone(), editor)
        module = after.apps.get_model('base', 'IrModule')
        row = module.objects.create(name='contract_category_long', category_path='Ω' * 101)

        with pytest.raises(IrreversibleError, match='100'):
            with connection.schema_editor() as editor:
                migration.unapply(state.clone(), editor)

        assert module.objects.get(pk=row.pk).category_path == 'Ω' * 101
        module.objects.filter(pk=row.pk).delete()
        with connection.schema_editor() as editor:
            migration.unapply(state.clone(), editor)


def test_category_reverse_preserves_a_relation_that_cannot_be_reconstructed():
    with historical_category_tables() as (state, (_, _, _)):
        migration = _migration()
        with connection.schema_editor() as editor:
            after = migration.apply(state.clone(), editor)
        category = after.apps.get_model('base', 'IrModuleCategory')
        module = after.apps.get_model('base', 'IrModule')
        node = category.objects.create(name='Manual relation')
        row = module.objects.create(
            name='contract_manual_relation', category_path='Unmapped', category_id=node.pk,
        )

        with pytest.raises(IrreversibleError, match='relación'):
            with connection.schema_editor() as editor:
                migration.unapply(state.clone(), editor)

        assert module.objects.get(pk=row.pk).category_id == node.pk
        module.objects.filter(pk=row.pk).delete()
        with connection.schema_editor() as editor:
            migration.unapply(state.clone(), editor)


def test_category_migration_does_not_overwrite_another_models_identity():
    with historical_category_tables() as (state, (category, identity, module)):
        module.objects.create(name='contract_foreign_identity', category='Sales')
        original = identity.objects.create(
            module='base', name='module_category_sales',
            model='base.IrModule', res_id=123, noupdate=True,
        )

        with pytest.raises(RuntimeError, match='incompatible'):
            with connection.schema_editor() as editor:
                _migration().apply(state.clone(), editor)

        original.refresh_from_db()
        assert (original.model, original.res_id) == ('base.IrModule', 123)
        assert module.objects.get(name='contract_foreign_identity').category == 'Sales'
        assert category.objects.count() == 0
