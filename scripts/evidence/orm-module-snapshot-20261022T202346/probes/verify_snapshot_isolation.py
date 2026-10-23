"""Dos bases propias y router existente: preparación de lectura, no instalación."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import django

django.setup()

from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.backends.db import SessionStore
from orm.routers import CompanyContextRequired
import orm.routers as router_module
from addons.base.models.ir_module import IrModule
from modules.module_graph import ModuleGraph
from orm.environments import company_scope
from service import db as database_service

run = Path(__file__).resolve().parent.parent
first = settings.DATABASES['default']['NAME']
assert first.startswith('orm_bootstrap_')
second = first + '_graph'
alias = 'company_97011_db'
container = os.environ['ORM_QA_CONTAINER']
marker = second
created = configured = False
results = {}
original_control_plane = router_module._CONTROL_PLANE_APPS


def admin(sql):
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                   input=sql, text=True, check=True)


try:
    settings.MULTIDB_MANAGEMENT_ENABLED = True
    assert not database_service.database_exists(second)
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'],
                   input=f'\nhost {second} {settings.DATABASES["default"]["USER"]} '
                         f'{os.environ["ORM_QA_BRIDGE"]}/32 scram-sha-256 # {marker}\n',
                   text=True, check=True)
    configured = True
    admin('SELECT pg_reload_conf();')
    database_service.create_empty_database(second)
    created = True
    definition = deepcopy(connections['default'].settings_dict)
    definition['NAME'] = second
    definition['TEST']['NAME'] = second
    settings.DATABASES[alias] = connections.databases[alias] = definition
    if '--metadata-contract' in sys.argv:
        if '--local-contenttypes' in sys.argv:
            router_module._CONTROL_PLANE_APPS = frozenset(original_control_plane - {'contenttypes'})
        targets = [('contenttypes', '0002_remove_content_type_name')]
        MigrationExecutor(connections['default']).migrate(targets + [('sessions', '0001_initial')])
        MigrationExecutor(connections[alias]).migrate(targets)
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT to_regclass('django_content_type'), to_regclass('django_session')")
            contenttypes_table, sessions_table = cursor.fetchone()
        assert contenttypes_table == 'django_content_type'
        assert sessions_table is None
        ContentType.objects.clear_cache()
        for using, label in [('default', 'contract_default'), (alias, 'contract_company')]:
            ContentType.objects.db_manager(using).create(id=99001, app_label=label, model='metadata')
        default = ContentType.objects.db_manager('default').get_for_id(99001)
        with company_scope(97011):
            company = ContentType.objects.get_for_id(99001)
            assert company.app_label == 'contract_company' and company._state.db == alias
            assert ContentType.objects.db_manager('default').get_for_id(99001).app_label == 'contract_default'
            session = SessionStore()
            session['contract_marker'] = 'central_session'
            session.save()
            assert SessionStore(session_key=session.session_key).load()['contract_marker'] == 'central_session'
            session.delete()
        assert default.app_label == 'contract_default' and default._state.db == 'default'
        with company_scope(999999):
            try:
                ContentType.objects.get_for_id(99001)
            except CompanyContextRequired:
                pass
            else:
                raise AssertionError('Unknown company must not fall back to central metadata')
        with company_scope(None):
            try:
                ContentType.objects.get_for_id(99001)
            except CompanyContextRequired:
                pass
            else:
                raise AssertionError('Missing company must not fall back to central metadata')
        results = {'metadata_alias_and_cache_isolation': True,
                   'same_primary_key_different_metadata': True,
                   'explicit_alias_overrides_company': True,
                   'missing_and_unknown_company_fail_closed': True,
                   'session_create_read_delete_remains_central': True,
                   'company_has_no_session_table': True,
                   'schema_created_by_native_migrations_only': True,
                   'scope': 'In-memory contenttypes placement hypothesis only; not full module installation or policy acceptance'}
        print(json.dumps(results, indent=2), flush=True)
        raise SystemExit(0)
    for using in ('default', alias):
        with connections[using].schema_editor() as editor:
            editor.create_model(IrModule)
        IrModule.objects.using(using).bulk_create([
            IrModule(name='base', state='installed', demo=using == 'default',
                     version='manifest-new', installed_version='installed-a' if using == 'default' else 'installed-b'),
            IrModule(name='uom', state='uninstalled' if using == 'default' else 'installed'),
            IrModule(name='product', state='installed'),
        ])
    with company_scope(97011):
        first_graph = ModuleGraph.from_database(['product'], using='default')
        second_graph = ModuleGraph.from_database(['product'], using=alias)
    assert first_graph.order() == ['base']
    assert second_graph.order() == ['base', 'uom', 'product']
    assert first_graph['base'].id == second_graph['base'].id
    assert first_graph['base'].installed_version == 'installed-a'
    assert second_graph['base'].installed_version == 'installed-b'
    assert first_graph['base'].demo and not second_graph['base'].demo
    assert first_graph.using == 'default' and second_graph.using == alias
    old_version = second_graph['base'].load_version
    second_graph['base'].installed_version = 'in-memory-only'
    second_graph['base'].state = 'to upgrade'
    assert second_graph['base'].load_version == old_version
    assert second_graph['base'].load_state == 'installed'
    persisted = IrModule.objects.using(alias).get(name='base')
    assert (persisted.installed_version, persisted.state) == ('installed-b', 'installed')
    update_graph = ModuleGraph.from_database(['product'], using='default', mode='update')
    assert update_graph.order() == ['base', 'uom', 'product']
    results = {'first_load_order':first_graph.order(), 'second_load_order':second_graph.order(),
               'first_update_order':update_graph.order(), 'same_primary_keys_do_not_merge_databases':True,
               'explicit_alias_wins_over_ambient_company':True, 'independent_demo_and_installed_version':True,
               'in_memory_mutation_preserves_initial_load_snapshot_and_database':True,
               'limits':'Only IrModule tables and real manifest graph; no loader/schema/data/hooks execution or effective registry acceptance'}
finally:
    router_module._CONTROL_PLANE_APPS = original_control_plane
    ContentType.objects.clear_cache()
    connections.close_all()
    settings.DATABASES.pop(alias, None)
    connections.databases.pop(alias, None)
    if hasattr(connections._connections, alias):
        delattr(connections._connections, alias)
    if created:
        database_service.drop_database(second)
    if configured:
        subprocess.run(['docker', 'exec', '-u', 'postgres', container, 'sh', '-c',
                        f"sed -i '/# {marker}$/d' \"$PGDATA/pg_hba.conf\""], check=True)
        admin('SELECT pg_reload_conf();')
    results['second_database_removed'] = not database_service.database_exists(second)
    (run/('outputs/contenttypes-local-metadata.json' if '--metadata-contract' in sys.argv else 'outputs/snapshot-isolation.json')).write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
