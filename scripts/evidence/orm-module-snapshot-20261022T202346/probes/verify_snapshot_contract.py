"""Controles propietarios del snapshot contra PostgreSQL propio, esquema reducido."""
import importlib.util
from pathlib import Path

import django
import pytest

django.setup()

from django.conf import settings
from django.db import connection, transaction
from addons.base.models.ir_module import IrModule

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
spec = importlib.util.spec_from_file_location('snapshot_contracts', Path.cwd()/'tests/integration/base/test_module_graph_database.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
with connection.schema_editor() as editor:
    editor.create_model(IrModule)
cases = [(name, ()) for name in (
    'test_snapshot_copies_persisted_identity_state_demo_and_installed_version',
    'test_snapshot_does_not_invent_unknown_installed_versions',
    'test_empty_snapshot_does_not_query', 'test_snapshot_rejects_unknown_database',
    'test_snapshot_does_not_remove_an_already_pruned_row_twice')]
cases += [('test_snapshot_mode_filters_and_prunes_dependents', (mode, state))
          for mode in ('load', 'update') for state in (
              'installed', 'to upgrade', 'to remove', 'to install', 'uninstalled', 'uninstallable')]
cases += [('test_snapshot_preparation_prunes_unloadable_code', (problem,))
          for problem in ('cycle', 'uninstallable_manifest', 'missing_manifest')]
failed = 0
for name, args in cases:
    try:
        with transaction.atomic(), pytest.MonkeyPatch.context() as patcher:
            manifests = tests.graph_manifests.__wrapped__(patcher)
            getattr(tests, name)(manifests, *args)
            transaction.set_rollback(True)
        print('PASS', name, *args)
    except Exception as error:
        failed += 1
        print('FAIL', name, *args, type(error).__name__, str(error))
print(f'{len(cases)-failed} PASS, {failed} FAIL; real PostgreSQL, minimal schema, not full loader acceptance')
raise SystemExit(bool(failed))
