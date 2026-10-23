"""Ejecuta los controles propietarios sobre tablas propias, sin reconstruir QA."""
import importlib.util
from pathlib import Path
import traceback

import django
import pytest

django.setup()

from django.conf import settings
from django.db import connection, transaction
from addons.base.models.ir_module import IrModule, IrModuleDependency, IrModuleExclusion
from addons.base_automation.models.base_automation import BaseAutomation

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
root = Path.cwd()
spec = importlib.util.spec_from_file_location('catalog_contracts', root/'tests/integration/base/test_module_catalog_database.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
with connection.schema_editor() as editor:
    for model in (IrModule, IrModuleDependency, IrModuleExclusion):
        editor.create_model(model)
failed = 0
names = ['test_refresh_preserves_installed_version_when_manifest_changes',
         'test_new_catalog_entry_has_unknown_installed_version',
         'test_dry_run_preserves_both_version_sources']
for name in names:
    try:
        with transaction.atomic(), pytest.MonkeyPatch.context() as patcher:
            # El esquema reducido no incluye automatizaciones; no cualifica sus hooks.
            patcher.setattr(BaseAutomation, "_get_actions", classmethod(lambda cls, *args: []))
            manifests = tests.manifests.__wrapped__(patcher)
            getattr(tests, name)(manifests)
            transaction.set_rollback(True)
        print('PASS', name)
    except Exception:
        failed += 1
        print('FAIL', name)
        traceback.print_exc()
print(f'{len(names)-failed} PASS, {failed} FAIL; real PostgreSQL, minimal model schema; not full migration/bootstrap acceptance')
raise SystemExit(bool(failed))
