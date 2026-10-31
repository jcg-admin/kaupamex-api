"""Sonda Consumer: dos bases propias, router real y registros existentes."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess

import django
django.setup()

from django.conf import settings
from django.db import connections, router, transaction
from django.db.migrations.executor import MigrationExecutor

from addons.base.models import IrModule
from modules.module_graph import build_graph
from orm.environments import company_scope, get_current_company
from orm.registry import Registry
from service import db as database_service

run = Path(__file__).resolve().parent.parent
name_a = settings.DATABASES['default']['NAME']
assert name_a.startswith('orm_bootstrap_'), 'Use the existing exclusive PostgreSQL harness.'
name_b = name_a + '_b'
container = os.environ['ORM_QA_CONTAINER']
marker = 'module_' + name_a
alias_a, alias_b = 'company_97001_db', 'company_97002_db'
results = {}


def admin(sql):
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                   input=sql, text=True, check=True)


def row_names(company):
    try:
        with company_scope(company):
            return sorted(IrModule.objects.values_list('name', flat=True))
    finally:
        connections.close_all()


async def context_probe():
    async def read(company):
        with company_scope(company):
            await asyncio.sleep(0)
            return get_current_company()
    return await asyncio.gather(read(97001), read(97002))


created = hba_added = False
original_management = getattr(settings, 'MULTIDB_MANAGEMENT_ENABLED', None)
try:
    # El backend Consumer crea/elimina la base; no se implementa otro provisioner.
    settings.MULTIDB_MANAGEMENT_ENABLED = True
    assert not database_service.database_exists(name_b)
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'],
                   input=f'\nhost {name_b} {settings.DATABASES["default"]["USER"]} '
                         f'{os.environ["ORM_QA_BRIDGE"]}/32 scram-sha-256 # {marker}\n',
                   text=True, check=True)
    hba_added = True
    admin('SELECT pg_reload_conf();')
    database_service.create_empty_database(name_b)
    created = True
    for alias, name in ((alias_a, name_a), (alias_b, name_b)):
        definition = deepcopy(connections['default'].settings_dict)
        definition['NAME'] = name
        definition['TEST']['NAME'] = name
        settings.DATABASES[alias] = definition
        connections.databases[alias] = definition
        with connections[alias].schema_editor() as editor:
            editor.create_model(IrModule)

    names_a = build_graph(['base']).order()
    names_b = build_graph(['product']).order()
    for alias, names in ((alias_a, names_a), (alias_b, names_b)):
        # Fixtures de estado: bulk_create no dispara hooks de otros addons cuyo
        # esquema esta sonda NO instala. No acredita save/instalación completos.
        IrModule.objects.using(alias).bulk_create(
            [IrModule(name=name, state='installed') for name in names])
    results['fixture_scope'] = 'Only IrModule tables and manifest-derived state fixtures; NOT a completed module installation.'
    results['manifest_closures'] = {'a': names_a, 'b': names_b}
    results['independent_state_rows'] = {
        'a': sorted(IrModule.objects.using(alias_a).values_list('name', flat=True)),
        'b': sorted(IrModule.objects.using(alias_b).values_list('name', flat=True)),
    }
    results['routing'] = {}
    for company, alias in ((97001, alias_a), (97002, alias_b)):
        with company_scope(company):
            IrModule.objects.filter(name='base').update(shortdesc=str(company))
            results['routing'][str(company)] = {
                'read_alias': router.db_for_read(IrModule),
                'write_alias': router.db_for_write(IrModule),
                'expected': alias,
                'names': sorted(IrModule.objects.values_list('name', flat=True)),
                'written_label_on_expected_database': IrModule.objects.using(alias).get(name='base').shortdesc,
            }
    a = IrModule.objects.using(alias_a).get(name='base')
    b = IrModule.objects.using(alias_b).get(name='base')
    with company_scope(97001):
        results['cross_database_relation_allowed'] = router.allow_relation(a, b)
    for alias in (alias_a, alias_b):
        try:
            with transaction.atomic(using=alias):
                IrModule.objects.using(alias).bulk_create(
                    [IrModule(name='rollback_probe', state='installed')])
                raise ValueError('rollback control')
        except ValueError:
            pass  # silent OK because la excepción inyectada verifica el rollback.
    results['rollback_preserved'] = all(not IrModule.objects.using(a).filter(name='rollback_probe').exists()
                                        for a in (alias_a, alias_b))
    with connections[alias_b].cursor() as cursor:
        try:
            with transaction.atomic(using=alias_b):
                cursor.execute('CREATE TABLE orm_ddl_rollback_probe (id integer)')
                raise ValueError('DDL rollback control')
        except ValueError:
            pass  # silent OK because el DDL debe desaparecer al revertir la transacción.
        cursor.execute("SELECT to_regclass('orm_ddl_rollback_probe')")
        results['ddl_rollback_preserved'] = cursor.fetchone()[0] is None
        cursor.execute('SHOW server_version')
        results['postgresql_version'] = cursor.fetchone()[0]
    results['async_contexts'] = asyncio.run(context_probe())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results['concurrent_rows'] = list(pool.map(row_names, (97001, 97002)))
    results['main_context_restored'] = get_current_company() is None
    registries = [Registry.new(a) for a in (alias_a, alias_b)]
    results['registry'] = {
        'distinct_instances': registries[0] is not registries[1],
        'separate_maps': registries[0].models is not registries[1].models,
        'same_model_names': set(registries[0].models) == set(registries[1].models),
        'product_models_in_a': sorted(k for k, v in registries[0].models.items()
                                      if getattr(getattr(v, '_meta', None), 'app_label', None) == 'product'),
        'product_models_in_b': sorted(k for k, v in registries[1].models.items()
                                      if getattr(getattr(v, '_meta', None), 'app_label', None) == 'product'),
        'process_model_classes_shared': all(registries[0].models[k] is v
                                           for k, v in registries[1].models.items()
                                           if k in registries[0].models),
    }
    # Hipótesis separada: historial de migraciones y esquema no son equivalentes
    # cuando un router omite contenttypes pero admite auth con FK a esa tabla.
    results['migration_executor'] = {}
    for alias in ('default', alias_b):
        executor = MigrationExecutor(connections[alias])
        target = [('auth', '0001_initial')]
        observed = {'plan': [list(m.key) if hasattr(m, 'key') else [m.app_label, m.name]
                             for m, backwards in executor.migration_plan(target)]}
        results['migration_executor'][alias] = observed
        try:
            executor.migrate(target)
            observed['status'] = 'PASS'
        except Exception as error:
            observed['status'] = 'FAIL'
            observed['exception'] = type(error).__name__
            observed['message'] = str(error)
            # Una FK diferida puede fallar al salir del schema editor. Se
            # descarta sólo el wrapper propio; el backend revierte su conexión
            # y ConnectionHandler crea la siguiente sin estado abortado.
            connections[alias].close()
            del connections[alias]
            observed['recovered_with_fresh_connection'] = True
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT to_regclass('django_content_type')")
            observed['contenttypes_table_exists'] = cursor.fetchone()[0] is not None
            cursor.execute("SELECT app, name FROM django_migrations ORDER BY app, name")
            observed['migration_history'] = [list(row) for row in cursor.fetchall()]
        results['migration_executor'][alias] = observed
finally:
    for alias in (alias_a, alias_b):
        Registry.delete(alias)
        if alias in connections.databases:
            connections[alias].close()
            del connections[alias]
            connections.databases.pop(alias, None)
            settings.DATABASES.pop(alias, None)
    if created:
        database_service.drop_database(name_b)
    if hba_added:
        subprocess.run(['docker', 'exec', '-u', 'postgres', container, 'sh', '-c',
                        f"sed -i '/# {marker}$/d' \"$PGDATA/pg_hba.conf\""], check=True)
        admin('SELECT pg_reload_conf();')
    settings.MULTIDB_MANAGEMENT_ENABLED = original_management
    results['second_database_removed'] = not database_service.database_exists(name_b)
    (run / 'outputs' / os.environ.get('ORM_PROBE_OUTPUT', 'database-contract.json')).write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False, indent=2))
