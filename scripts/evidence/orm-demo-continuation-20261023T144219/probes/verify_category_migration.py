"""Ejecuta controles mantenidos de migración en PostgreSQL propio sin QA global."""
from pathlib import Path
import runpy

import django

django.setup()

from django.conf import settings

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
root = Path(__file__).resolve().parents[4]
controls = runpy.run_path(str(root / 'tests/unit/modules/test_module_category_migration.py'))
for name in (
    'test_category_migration_preserves_paths_identity_state_and_version',
    'test_category_migration_refuses_ambiguous_identity_without_data_loss',
    'test_category_reverse_refuses_to_truncate_a_new_long_path',
    'test_category_reverse_preserves_a_relation_that_cannot_be_reconstructed',
    'test_category_migration_does_not_overwrite_another_models_identity',
):
    controls[name]()
    print(f'PASS: {name}', flush=True)
