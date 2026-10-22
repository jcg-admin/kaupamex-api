"""Capacidades nativas de migración en una base desechable, no un instalador."""
import json
from pathlib import Path

import django
django.setup()
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

assert connection.settings_dict['NAME'].startswith('orm_bootstrap_')
run = Path(__file__).resolve().parent.parent
results = {'scope': 'Native Django contenttypes migrations only, no addon lifecycle acceptance.'}


def columns():
    with connection.cursor() as cursor:
        return [field.name for field in connection.introspection.get_table_description(cursor, 'django_content_type')]


MigrationExecutor(connection).migrate([('contenttypes', '0001_initial')])
results['initial_columns'] = columns()
with connection.cursor() as cursor:
    cursor.execute("INSERT INTO django_content_type(app_label, model, name) VALUES (%s,%s,%s) RETURNING id",
                   ['module_probe', 'roundtrip', 'sentinel'])
    identity = cursor.fetchone()[0]
MigrationExecutor(connection).migrate([('contenttypes', '0002_remove_content_type_name')])
results['upgraded_columns'] = columns()
with connection.cursor() as cursor:
    cursor.execute('SELECT id,app_label,model FROM django_content_type WHERE id=%s', [identity])
    results['data_after_upgrade'] = list(cursor.fetchone())
assert 'name' in results['initial_columns'] and 'name' not in results['upgraded_columns']
assert results['data_after_upgrade'] == [identity, 'module_probe', 'roundtrip']
MigrationExecutor(connection).migrate([('contenttypes', '0001_initial')])
results['downgraded_columns'] = columns()
assert 'name' in results['downgraded_columns']
MigrationExecutor(connection).migrate([('contenttypes', None)])
with connection.cursor() as cursor:
    cursor.execute("SELECT to_regclass('django_content_type')")
    results['table_after_unapply'] = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM django_migrations WHERE app='contenttypes'")
    results['applied_migrations_after_unapply'] = cursor.fetchone()[0]
results['python_model_remains_registered'] = apps.get_model('contenttypes', 'ContentType') is not None
assert results['table_after_unapply'] is None and results['applied_migrations_after_unapply'] == 0
assert results['python_model_remains_registered']
results['status'] = 'PASS for native migration capabilities; NOT_EVALUATED addon install/upgrade/uninstall'
(run / 'outputs' / 'migration-roundtrip.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False, indent=2))
