"""Run maintained storage controls using existing owned PostgreSQL harness."""
from pathlib import Path
import runpy
import sys

import django

django.setup()

from django.conf import settings
from addons.base.models.ir_demo_failure import IrDemoFailure

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
root = Path(__file__).resolve().parents[4]
controls = runpy.run_path(str(root/'tests/unit/modules/test_demo_failure_storage.py'))
if '--annul-length' in sys.argv:
    IrDemoFailure._meta.get_field('error').max_length = 255
    print('Negative control: bounded error length restored only in memory', flush=True)
controls['test_complete_error_round_trips_without_truncation']()
if '--storage-only' not in sys.argv:
    controls['test_error_migration_preserves_history_and_refuses_lossy_reverse']()
print('PASS: complete error storage and requested migration controls')
