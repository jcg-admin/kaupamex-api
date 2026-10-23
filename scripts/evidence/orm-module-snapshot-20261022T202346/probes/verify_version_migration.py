"""Compatibilidad de la operación real sobre filas anteriores, PostgreSQL propio."""
import importlib
import json

import django

django.setup()

from django.conf import settings
from django.db import connection
from django.db.migrations.state import ModelState, ProjectState
from addons.base.models.ir_module import IrModule

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
migration = importlib.import_module('addons.base.migrations.0088_module_installed_version').Migration
assert migration.dependencies == [('base', '0087_module_lifecycle_states')]
assert len(migration.operations) == 1
operation = migration.operations[0]
assert operation.name == 'installed_version'
state = ProjectState()
state.add_model(ModelState.from_model(IrModule))
state.remove_field('base', 'irmodule', 'installed_version')
legacy = state.apps.get_model('base', 'IrModule')
with connection.schema_editor() as editor:
    editor.create_model(legacy)
legacy.objects.bulk_create([
    legacy(name='legacy_installed', version='19.0.9.9', state='installed'),
    legacy(name='legacy_pending', version='19.0.2.0', state='to install'),
])
after = state.clone()
operation.state_forwards('base', after)
with connection.schema_editor() as editor:
    operation.database_forwards('base', editor, state, after)
rows = list(IrModule.objects.order_by('name').values('name', 'version', 'state', 'installed_version'))
assert all(row['installed_version'] is None for row in rows)
assert rows[0]['version'] == '19.0.9.9' and rows[0]['state'] == 'installed'
assert rows[1]['version'] == '19.0.2.0' and rows[1]['state'] == 'to install'
field = IrModule._meta.get_field('installed_version')
assert field.null and not field.editable and field.max_length is None
assert field.deconstruct()[3] == operation.field.deconstruct()[3]
with connection.schema_editor() as editor:
    operation.database_backwards('base', editor, after, state)
assert legacy.objects.get(name='legacy_installed').version == '19.0.9.9'
print(json.dumps({'forward':rows,'reverse_preserves_legacy_metadata':True,
 'field_matches_model':True,'history_backfilled':False,
 'limits':'Real isolated AddField forward/reverse; not complete project migration graph acceptance'},indent=2))
