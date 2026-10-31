"""Introspección y experimentos aislados del stack realmente instalado."""
import hashlib
import importlib.metadata
import inspect
import json
import multiprocessing
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import django
django.setup()

from django.apps.config import AppConfig
from django.apps.registry import Apps
from django.db.models.base import ModelBase
from django.db.models.options import Options
from django.db import models
from django.db.utils import ConnectionRouter
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.executor import MigrationExecutor
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from gunicorn.arbiter import Arbiter
from gunicorn.workers.base import Worker

run = Path(__file__).resolve().parent.parent
interfaces = []
for owner, names in ((Apps, ('populate', 'register_model', 'get_model', 'get_models',
                            'lazy_model_operation', 'set_available_apps', 'set_installed_apps', 'clear_cache')),
                     (AppConfig, ('create', 'import_models', 'ready')),
                     (ModelBase, ('__new__',)), (Options, ('get_fields', 'get_field')),
                     (ConnectionRouter, ('db_for_read', 'db_for_write', 'allow_relation', 'allow_migrate')),
                     (MigrationLoader, ('build_graph',)), (MigrationExecutor, ('migrate',)),
                     (BaseDatabaseSchemaEditor, ('create_model', 'delete_model', 'alter_field')),
                     (Arbiter, ('spawn_worker',)), (Worker, ('init_process',))):
    for name in names:
        fn = inspect.unwrap(getattr(owner, name))
        source = inspect.getsourcefile(fn)
        lines, line = inspect.getsourcelines(fn)
        interfaces.append({'symbol': owner.__module__ + '.' + owner.__name__ + '.' + name,
                           'signature': str(inspect.signature(fn)), 'file': source,
                           'line': line, 'end_line': line + len(lines) - 1,
                           'sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest()})

isolated = Apps(installed_apps=[])
module = ModuleType('isolated_probe')
module.__file__ = str(run / 'probes' / 'stack_contract.py')
config = AppConfig('isolated_probe', module)
config.apps = isolated
config.models = isolated.all_models['isolated_probe']
isolated.app_configs['isolated_probe'] = config


class Before(models.Model):
    class Meta:
        app_label = 'isolated_probe'
        apps = isolated


isolated.set_installed_apps([])


class During(models.Model):
    class Meta:
        app_label = 'isolated_probe'
        apps = isolated


while_restricted = [m.__name__ for m in isolated.get_models()]
isolated.unset_installed_apps()
after_restore = [m.__name__ for m in isolated.get_models()]
assert while_restricted == [] and 'During' in after_restore

native_router = ConnectionRouter([])
cross_relation = native_router.allow_relation(SimpleNamespace(_state=SimpleNamespace(db='a')),
                                              SimpleNamespace(_state=SimpleNamespace(db='b')))
assert cross_relation is False
assert native_router.db_for_read(Before) == 'default'


def child_change(channel, state):
    state['generation'] = 1
    channel.send(state['generation'])
    channel.close()


state = {'generation': 0}
context = multiprocessing.get_context('fork')
parent, child = context.Pipe()
process = context.Process(target=child_change, args=(child, state))
process.start()
assert parent.poll(5)
child_value = parent.recv()
process.join(5)
assert process.exitcode == 0 and child_value == 1 and state['generation'] == 0
parent.close()
child.close()
result = {
    'versions': {'CPython': sys.version, **{name: importlib.metadata.version(name)
                 for name in ('Django', 'djangorestframework', 'psycopg', 'gunicorn', 'lxml')}},
    'interfaces': interfaces,
    'experiments': {
        'apps_restore_keeps_imported_models': {'while_restricted': while_restricted,
                                              'after_restore': after_restore,
                                              'verdict': 'PASS: observed retention; NOT a production installer'},
        'native_router_no_selection_falls_back_to_default': 'PASS',
        'native_router_rejects_bound_cross_database_relation': 'PASS',
        'process_memory_does_not_propagate_registry_updates': {'parent': state['generation'],
                                                              'child': child_value, 'verdict': 'PASS'},
    },
    'limitations': ['No changes to global Django apps, installed stack or production settings.',
                    'Gunicorn worker lifecycle inspected in installed source; no live multiworker reload acceptance.',
                    'Process experiment demonstrates memory separation, not an existing cross-process coordinator.',
                    'No native Odoo test runtime was executed.'],
}
(run / 'outputs' / 'stack-contract.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'versions': result['versions'], 'interfaces': len(interfaces),
                  'experiments': result['experiments'], 'limitations': result['limitations']}, ensure_ascii=False, indent=2))
