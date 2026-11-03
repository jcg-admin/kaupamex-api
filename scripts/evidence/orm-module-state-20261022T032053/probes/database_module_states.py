"""Dos bases propias: catálogo y solicitudes administrativas sin simular instalación."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import django

django.setup()

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connections, transaction
from django.test.utils import CaptureQueriesContext
from addons.authz.declaration import values_from_manifest
from addons.base.models.ir_module import IrModule, IrModuleDependency, IrModuleExclusion
from addons.base.management.commands import update_module_list as catalog
from modules.module import load_manifest
from orm.environments import sudo
from service import db as database_service

run = Path(__file__).resolve().parent.parent
name_a = settings.DATABASES['default']['NAME']
assert name_a.startswith('orm_bootstrap_')
name_b = name_a + '_modules'
alias_b = 'company_97011_db'
marker = name_b
container = os.environ['ORM_QA_CONTAINER']
modules = ['base', 'uom', 'product']
manifests = {name: load_manifest(name) for name in modules}
assert all(manifests.values())
assert set().union(*(set(m.get('depends', [])) for m in manifests.values())) <= set(modules)
results = {'fixture_manifests': {name: {'depends': m.get('depends', [])} for name, m in manifests.items()}}


def admin(sql):
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                   input=sql, text=True, check=True)


def state(using):
    return dict(IrModule.objects.using(using).values_list('name', 'state'))


created = hba_added = False
try:
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
    configuration = deepcopy(settings.DATABASES['default'])
    configuration['NAME'] = name_b
    settings.DATABASES[alias_b] = configuration
    connections.databases[alias_b] = configuration
    for using in ('default', alias_b):
        with connections[using].schema_editor() as editor:
            for model in (IrModule, IrModuleDependency, IrModuleExclusion):
                editor.create_model(model)
        fixture = []
        for name, manifest in manifests.items():
            values = values_from_manifest(catalog.read_manifest(catalog.get_module_path(name)))
            values.pop('depends')
            values.pop('installable')
            values['state'] = 'installed' if using == alias_b or name == 'base' else 'uninstalled'
            fixture.append(IrModule(name=name, **values))
        IrModule.objects.using(using).bulk_create(fixture)
        rows = {r.name: r.pk for r in IrModule.objects.using(using).all()}
        IrModuleDependency.objects.using(using).bulk_create([
            IrModuleDependency(module_id=rows[name], name=dep)
            for name, manifest in manifests.items() for dep in manifest.get('depends', [])])
    original_a, original_b = state('default'), state(alias_b)
    observed_dependencies = {}
    for using in ('default', alias_b):
        edge = IrModuleDependency.objects.using(using).get(module__name='product', name='uom')
        observed_dependencies[using] = edge._compute_state()
    assert observed_dependencies == {'default': 'uninstalled', alias_b: 'installed'}
    results['dependency_states'] = observed_dependencies
    edges = [IrModuleDependency.objects.using(using).get(module__name='product', name='uom')
             for using in ('default', alias_b)]
    assert edges[0].pk == edges[1].pk
    try:
        IrModuleDependency._compute_depend_batch(edges)
    except ValidationError as error:
        results['mixed_database_batch_rejected'] = str(error)
    else:
        raise AssertionError('A batch with colliding IDs from two databases must be rejected')
    with ExitStack() as stack:
        stack.enter_context(patch.object(catalog, 'get_modules', return_value=modules))
        stack.enter_context(patch.object(catalog.Command, '_report_auto_install_gaps'))
        for using in ('default', alias_b):
            call_command('update_module_list', database=using, verbosity=0)
    assert state('default') == original_a
    assert state(alias_b) == original_b
    results['catalog_preserves_distinct_states'] = {'a': original_a, 'b': original_b}
    with sudo(), transaction.atomic(using='default'):
        selected = IrModule.objects.using('default').get(name='product').button_install()
        assert selected == ['base', 'uom', 'product']
        assert state('default') == {'base': 'installed', 'uom': 'to install', 'product': 'to install'}
        assert state(alias_b) == original_b
        results['install_request'] = {'order': selected, 'a': state('default'), 'b': state(alias_b)}
        transaction.set_rollback(True, using='default')
    with sudo(), transaction.atomic(using=alias_b):
        IrModule.objects.using(alias_b).get(name='uom').button_upgrade()
        assert state(alias_b) == {'base': 'installed', 'uom': 'to upgrade', 'product': 'to upgrade'}
        assert state('default') == original_a
        results['upgrade_request'] = state(alias_b)
        transaction.set_rollback(True, using=alias_b)
    with sudo(), transaction.atomic(using=alias_b):
        selected = IrModule.objects.using(alias_b).get(name='uom').button_uninstall()
        assert selected == ['product', 'uom']
        assert state(alias_b) == {'base': 'installed', 'uom': 'to remove', 'product': 'to remove'}
        assert state('default') == original_a
        results['uninstall_request'] = state(alias_b)
        transaction.set_rollback(True, using=alias_b)
    assert state('default') == original_a and state(alias_b) == original_b
    results['rollback_restores_states'] = True

    def concurrent_request(using, operation):
        try:
            with sudo(), transaction.atomic(using=using):
                module = IrModule.objects.using(using).get(name='product')
                getattr(module, operation)()
                observed = state(using)
                transaction.set_rollback(True, using=using)
                return observed
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(concurrent_request, 'default', 'button_install')
        b = pool.submit(concurrent_request, alias_b, 'button_upgrade')
        observed_a, observed_b = a.result(timeout=10), b.result(timeout=10)
    assert observed_a['product'] == 'to install'
    assert observed_b['product'] == 'to upgrade'
    assert state('default') == original_a and state(alias_b) == original_b
    results['concurrent_requests'] = {'a': observed_a, 'b': observed_b, 'rollback_restored': True}
    batch = list(IrModuleDependency.objects.using(alias_b).all())
    with CaptureQueriesContext(connections[alias_b]) as captured:
        resolved = IrModuleDependency._compute_depend_batch(batch)
    assert len(captured) == 1
    assert all(module._state.db == alias_b for module in resolved.values())
    results['bound_batch_query_count'] = len(captured)
    with sudo(), transaction.atomic(using=alias_b):
        owner = IrModule.objects.using(alias_b).get(name='product')
        IrModuleExclusion.objects.using(alias_b).bulk_create([
            IrModuleExclusion(module_id=owner.pk, name='uom')])
        excluded = IrModuleExclusion.objects.using(alias_b).get(module_id=owner.pk)
        assert excluded._compute_state() == 'installed'
        results['bound_exclusion_state'] = excluded._compute_state()
        transaction.set_rollback(True, using=alias_b)
    results['acceptance_limit'] = 'Requests only. No addon schema/data/hooks execution or effective registry acceptance.'
finally:
    connections.close_all()
    settings.DATABASES.pop(alias_b, None)
    connections.databases.pop(alias_b, None)
    if hasattr(connections._connections, alias_b):
        delattr(connections._connections, alias_b)
    if created:
        database_service.drop_database(name_b)
    if hba_added:
        subprocess.run(['docker', 'exec', '-u', 'postgres', container, 'sh', '-c',
                        f"sed -i '/# {marker}$/d' \"$PGDATA/pg_hba.conf\""], check=True)
        admin('SELECT pg_reload_conf();')
    results['second_database_removed'] = not database_service.database_exists(name_b)
    (run/'outputs/database-module-states.json').write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps(results, indent=2))
