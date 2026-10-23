"""Run the maintained historical migration controls on own PostgreSQL only."""
import importlib
from pathlib import Path
import runpy
import sys

import django

django.setup()

from django.conf import settings

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
root = Path(__file__).resolve().parents[4]
controls = runpy.run_path(str(root/'tests/unit/website_sale/test_salesteam_migration.py'))
if '--annul-separation' in sys.argv:
    migration = importlib.import_module(
        'addons.website_sale.migrations.0003_websitesalesettings_salesteam_and_more').Migration
    migration.operations = [*migration.operations[0].state_operations, *migration.operations[1:]]
    print('Negative: runtime default restored during historical DDL in memory only', flush=True)
for state in [None, True, False, 'missing', 'wrong_model']:
    controls['test_historical_migration_preserves_local_default_without_live_models'](state)
    message = ('identity mismatch rejected, historical row preserved' if state == 'wrong_model' else
               'historical forward/reverse, runtime lookup absent, selected alias only')
    print('PASS: '+message+'; team='+str(state), flush=True)
for company, alias in [(None, 'default'), (77421, 'company_77421_db')]:
    controls['test_runtime_default_uses_existing_router_binding'](company, alias)
    print('PASS: runtime router alias '+alias, flush=True)
