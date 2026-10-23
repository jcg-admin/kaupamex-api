"""TASK-API-0383: migraciones reales default/company con recursos propios."""
import json
import hashlib
from pathlib import Path
import secrets
import subprocess
import os
import time
import sys

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.backends.db import SessionStore
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.executor import MigrationExecutor
from orm.environments import company_scope
from orm.routers import CompanyDatabaseRouter
import orm.routers as router_module
from service import db as database_service

run = Path(os.environ.get('ORM_COMPANY_EVIDENCE_DIR', str(Path(__file__).resolve().parent.parent)))
first = settings.DATABASES['default']['NAME']
assert first.startswith('orm_bootstrap_')
company = 'company_' + str(secrets.randbits(48)) + '_db'
container = os.environ['ORM_QA_CONTAINER']
marker = first + '_full_company'
created = hba = False
results = {'task':'TASK-API-0383','scope':'Full Django migration verification only, not module installer execution or Task acceptance','databases':{}}
results['instrument_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def admin(sql):
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                   input=sql,text=True,check=True)


def observe(alias):
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT to_regclass('res_users'), to_regclass('res_company'), to_regclass('ir_module_module')")
        backbone = cursor.fetchone()
        assert all(backbone), (alias,backbone)
        cursor.execute("SELECT count(*) FROM pg_constraint c JOIN pg_class p ON p.oid=c.confrelid WHERE c.contype='f' AND p.relname='res_users'")
        user_keys = cursor.fetchone()[0]
        assert user_keys > 0
        cursor.execute("SELECT is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='ir_module_module' AND column_name='installed_version'")
        assert cursor.fetchone() == ('YES',)
        cursor.execute('SELECT count(*),count(installed_version) FROM ir_module_module')
        versions = cursor.fetchone()
    applied = MigrationRecorder(connections[alias]).applied_migrations()
    assert ('base','0088_module_installed_version') in applied
    return {'backbone_tables':backbone,'foreign_keys_to_local_res_users':user_keys,
            'applied_migrations':len(applied),'installed_version_nullable':True,
            'catalogue_rows':versions[0],'rows_with_installed_version':versions[1]}


try:
    settings.MULTIDB_MANAGEMENT_ENABLED = True
    assert not database_service.database_exists(company)
    started = time.monotonic()
    if '--diagnose-contenttypes' in sys.argv or '--company-only' in sys.argv:
        results['default_migration_skipped_for_bounded_diagnostic'] = True
    elif '--reuse-default' in sys.argv:
        print('Verify and reuse already migrated owned CI default database', flush=True)
        results['default_schema_reused_from_current_ci'] = True
    else:
        print('Begin full default migration on owned disposable database', flush=True)
        call_command('migrate',database='default',run_syncdb=True,verbosity=0)
    if '--diagnose-contenttypes' not in sys.argv and '--company-only' not in sys.argv:
        results['databases']['default'] = observe('default')
    results['default_migration_seconds'] = round(time.monotonic()-started,3)
    if results['databases'].get('default'):
        print('Full default migration and backbone/FK checks PASS',flush=True)
    else:
        print('Default migration NOT_EVALUATED in bounded company diagnostic', flush=True)
    subprocess.run(['docker','exec','-i','-u','postgres',container,'sh','-c','cat >> "$PGDATA/pg_hba.conf"'],
                   input=f'\nhost {company} {settings.DATABASES["default"]["USER"]} {os.environ["ORM_QA_BRIDGE"]}/32 scram-sha-256 # {marker}\n',text=True,check=True)
    hba = True
    admin('SELECT pg_reload_conf();')
    # Crear antes permite limpiar incluso si migrate dentro del provisionador falla.
    database_service.create_empty_database(company)
    created = True
    started = time.monotonic()
    print('Begin existing company provisioner on owned disposable database',flush=True)
    if '--diagnose-contenttypes' in sys.argv:
        database_service.install_company_aliases(settings.DATABASES, [company])
        connection = connections[company]
        executor = MigrationExecutor(connection)
        target = [('contenttypes', '0002_remove_content_type_name')]
        results['migration_plan'] = [list(migration.key) if hasattr(migration, 'key') else [migration.app_label, migration.name]
                                     for migration, backwards in executor.migration_plan(target)]
        router = CompanyDatabaseRouter()
        results['routing'] = {
            'company_contenttypes': router.allow_migrate(company, 'contenttypes', 'contenttype'),
            'default_contenttypes': router.allow_migrate('default', 'contenttypes', 'contenttype'),
            'unknown_company_contenttypes': router.allow_migrate('company_999999999999999999999999_db', 'contenttypes', 'contenttype'),
            'company_domain': router.allow_migrate(company, 'base', 'iractionsserver'),
        }
        with company_scope(company.split('_')[1]):
            executor.migrate(target)
        applied = MigrationRecorder(connection).applied_migrations()
        results['contenttypes_recorded_applied'] = all(key in applied for key in target)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), to_regclass('django_content_type')")
            actual_database, table = cursor.fetchone()
        results['actual_database_is_requested_company'] = actual_database == company
        results['contenttypes_table'] = table
        migration = executor.loader.get_migration('base', '0060_iractionsserver_crud_model_id_and_more')
        results['failing_migration_dependencies'] = migration.dependencies
        results['contenttypes_foreign_key_operations'] = [operation.name for operation in migration.operations
            if getattr(getattr(operation, 'field', None), 'remote_field', None)
            and operation.field.remote_field.model == 'contenttypes.contenttype']
        assert results['actual_database_is_requested_company']
        assert results['contenttypes_recorded_applied']
        assert table is None
        assert results['contenttypes_foreign_key_operations'] == ['resource_ref_content_type']
        results['classification'] = 'Confirmed router exclusion, not absent dependency ordering; functional provisioning remains FAIL'
        print(json.dumps(results, indent=2), flush=True)
        raise SystemExit(0)
    if '--probe-local-contenttypes' in sys.argv:
        original_control_plane = router_module._CONTROL_PLANE_APPS
        router_module._CONTROL_PLANE_APPS = frozenset(original_control_plane - {'contenttypes'})
        results['experimental_override'] = 'In-memory only: contenttypes follows selected company; sessions unchanged. Not production acceptance.'
    name, was_created = database_service.provision_company_database(company)
    assert name == company and not was_created
    results['databases']['company'] = observe(company)
    results['company_migration_seconds'] = round(time.monotonic()-started,3)
    if 'default' in results['databases']:
        assert results['databases']['default']['applied_migrations'] == results['databases']['company']['applied_migrations']
        assert results['databases']['default']['foreign_keys_to_local_res_users'] == results['databases']['company']['foreign_keys_to_local_res_users']
    results['separate_physical_databases'] = first != company
    if '--probe-local-contenttypes' in sys.argv or '--verify-metadata-session-cycle' in sys.argv:
        # Measure storage independently from authentication/identity acceptance.
        results['metadata_session_probe'] = {'status': 'running'}
        with company_scope(company.split('_')[1]):
            marker_name = 'local_' + secrets.token_hex(8)
            assert not ContentType.objects.db_manager('default').filter(
                app_label='contract_bootstrap', model=marker_name).exists()
            local_type = ContentType.objects.db_manager(company).create(
                app_label='contract_bootstrap', model=marker_name)
            assert ContentType.objects.db_manager(company).get_for_id(local_type.pk).model == marker_name
            try:
                central_type = ContentType.objects.db_manager('default').get_for_id(local_type.pk)
            except ContentType.DoesNotExist:
                central_type = None
            assert central_type is None or central_type.model != marker_name
            assert not ContentType.objects.db_manager('default').filter(
                app_label='contract_bootstrap', model=marker_name).exists()
            store = SessionStore()
            store['company_probe'] = company
            store.create()
            old_key = store.session_key
            assert SessionStore(old_key).load()['company_probe'] == company
            store.cycle_key()
            new_key = store.session_key
            assert new_key != old_key and not store.exists(old_key)
            assert SessionStore(new_key).load()['company_probe'] == company
            session_model = store.get_model_class()
            assert session_model.objects.using('default').filter(session_key=new_key).exists()
            assert 'django_session' not in connections[company].introspection.table_names()
            store.flush()
            assert not SessionStore().exists(new_key)
            local_type.delete(using=company)
        results['metadata_session_probe'] = {
            'status': 'pass', 'local_metadata_not_in_default': True,
            'content_type_cache_bound_to_alias': True,
            'session_create_rotate_read_flush': True,
            'session_storage_default_only': True,
            'session_keys_removed': True,
            'limit': 'Storage backend under one company context and separate default DB. Not login, cross-company user identity, authorization or productive policy acceptance.',
        }
    results['limits'] = 'Migration/schema acceptance only. No module graph execution, data/demo/hooks lifecycle, ORM compute conformance or PR integration.'
    print('Full company migration and independent backbone/FK checks PASS',flush=True)
finally:
    if results.get('metadata_session_probe', {}).get('status') == 'running':
        results['metadata_session_probe']['status'] = 'failed'
    if '--probe-local-contenttypes' in sys.argv and 'original_control_plane' in locals():
        router_module._CONTROL_PLANE_APPS = original_control_plane
    connections.close_all()
    settings.DATABASES.pop(company,None)
    connections.databases.pop(company,None)
    if hasattr(connections._connections,company):
        delattr(connections._connections,company)
    if created:
        database_service.drop_database(company)
    if hba:
        subprocess.run(['docker','exec','-u','postgres',container,'sh','-c',f"sed -i '/# {marker}$/d' \"$PGDATA/pg_hba.conf\""],check=True)
        admin('SELECT pg_reload_conf();')
    results['company_database_removed'] = not database_service.database_exists(company)
    (run/('outputs/contenttypes-routing-diagnostic.json' if '--diagnose-contenttypes' in sys.argv else 'outputs/company-local-contenttypes-experiment.json' if '--probe-local-contenttypes' in sys.argv else 'outputs/full-company-migrations.json')).write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
