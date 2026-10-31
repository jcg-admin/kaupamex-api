"""Run the maintained migration control on the existing disposable PG harness."""
import runpy
import importlib
import sys
from pathlib import Path

import django
from django.conf import settings

django.setup()
assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
root = Path(__file__).resolve().parents[4]
control = runpy.run_path(str(root/'tests/unit/hr/test_payroll_calendar_migration.py'))
if '--annul-separation' in sys.argv:
    migration = importlib.import_module('addons.hr.migrations.0004_hrpayrollstructuretype_default_resource_calendar').Migration
    migration.operations = migration.operations[0].state_operations
    print('Negative control: historical/runtime default separation annulled only in memory', flush=True)
control['test_calendar_migration_preserves_rows_without_live_defaults']()
print('PASS: historical DDL does not query live models; rows/NULL/callable state/reverse preserved')
