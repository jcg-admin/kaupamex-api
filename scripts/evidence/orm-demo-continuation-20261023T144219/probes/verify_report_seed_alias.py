"""Verifica reparación por alias y rollback en PostgreSQL propio."""
import argparse
from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path

import django
from django.conf import settings
from django.db import connection, connections, transaction
from django.db.migrations.loader import MigrationLoader


parser = argparse.ArgumentParser()
parser.add_argument('--result', type=Path, required=True)
arguments = parser.parse_args()
django.setup()
assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
cases = [
    ('sale', '0013_align_report_template_type', 'sale.report_saleorder'),
    ('sale_stock', '0004_align_report_template_type',
     'sale_stock.report_saleorder_incoterm'),
]
apps = MigrationLoader(connection).project_state([
    (app, name) for app, name, _key in cases
]).apps
view = apps.get_model('base', 'IrUiView')
keys = [key for _app, _name, key in cases]
before = list(view.objects.filter(key__in=keys).order_by('pk').values())
assert len(before) == 2
assert all(row['type'] == 'template' for row in before)
alias = 'report_seed_contract_alias'
assert alias not in connections.databases
connections.databases[alias] = deepcopy(settings.DATABASES['default'])
database = connections[alias]


def reject_default(execute, sql, params, many, context):
    raise AssertionError('Repair accessed default instead of selected alias')


try:
    with transaction.atomic(using=alias):
        view.objects.using(alias).filter(key__in=keys).update(type='qweb')
        with connection.execute_wrapper(reject_default):
            for app, name, key in cases:
                migration = import_module(f'addons.{app}.migrations.{name}')
                with database.schema_editor() as editor:
                    migration.align_report_template_type(apps, editor)
            after = list(view.objects.using(alias).filter(
                key__in=keys).order_by('pk').values())
            assert after == before
        transaction.set_rollback(True, using=alias)
finally:
    database.close()
    del connections[alias]
    connections.databases.pop(alias, None)
assert list(view.objects.filter(key__in=keys).order_by('pk').values()) == before
result = {
    'passed': True, 'selected_alias': alias,
    'default_sql_rejected_during_repair': True,
    'all_row_values_preserved_after_repair': True,
    'rollback_verified': True, 'alias_cleanup': True,
    'scope': 'Two connections to own PostgreSQL database; not N>1 physical acceptance',
}
arguments.result.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
