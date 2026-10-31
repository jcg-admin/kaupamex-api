"""Cualifica snapshots del grafo en bases físicas propias, sin instalar addons."""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from unittest import mock

import django

django.setup()

from django.conf import settings
from django.db import connections
from modules.module_graph import ModuleGraph
from service import db as svc

root = Path.cwd()
role = settings.DATABASES['default']['USER']
assert re.fullmatch(r'orm_bootstrap_[0-9a-f]{12}', role)
assert settings.DATABASES['default']['NAME'] == role
settings.MULTIDB_MANAGEMENT_ENABLED = True
container = os.environ['ORM_QA_CONTAINER']
marker = role + '_physical_graph'
names = ['company_%s_db' % secrets.randbits(48) for _ in range(2)]
assert len(set(names)) == 2
source = root / 'tests/integration/company/test_multidb_isolation.py'
spec = importlib.util.spec_from_file_location('existing_isolation_fixture', source)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
output = Path(__file__).resolve().parents[1] / 'outputs'
mode = 'wrong-alias' if '--wrong-alias' in sys.argv else (
    'partial-failure' if '--fail-after-first-create' in sys.argv else 'positive')
result = {'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'task': 'TASK-API-0382', 'mode': mode, 'databases': names,
          'scope': 'Physical catalogue and graph snapshot only; no schema completeness, Registry, authentication or module installation acceptance',
          'fixture': 'Minimal ir_module_module rows and controlled manifests; native service create/drop/aliases plus existing qualified _forget_alias',
          'acceptance': 'not_verified'}


def admin(sql):
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container, 'psql',
                    '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                   input=sql, text=True, check=True)


hba = False
error = None
try:
    admin(f'ALTER ROLE {role} CREATEDB;')
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'], input=
                   f'\nhost all {role} {os.environ["ORM_QA_BRIDGE"]}/32 scram-sha-256 # {marker}\n',
                   text=True, check=True)
    hba = True
    admin('SELECT pg_reload_conf();')
    with ExitStack() as resources:
        for name in names:
            assert not svc.database_exists(name)
            svc.create_empty_database(name)
            resources.callback(fixture._forget_alias, name)
            resources.callback(svc.drop_database, name)
            if '--fail-after-first-create' in sys.argv:
                raise RuntimeError('Injected after acquiring first physical database')
        svc.install_company_aliases(settings.DATABASES, names)
        identities = []
        snapshots = {}
        for index, name in enumerate(names):
            with connections[name].cursor() as cursor:
                cursor.execute('SELECT current_database()')
                identities.append(cursor.fetchone()[0])
                assert identities[-1] == name
                cursor.execute('CREATE TABLE ir_module_module (id integer PRIMARY KEY, '
                               'name varchar(128), state varchar(32), demo boolean, '
                               'installed_version varchar(128))')
                cursor.execute('INSERT INTO ir_module_module VALUES '
                               '(%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s)',
                               [1000 * (index + 1), 'base', 'installed', index == 0,
                                'catalogue-%s' % index, 1000 * (index + 1) + 1,
                                'physical_child', 'installed' if index == 0 else 'uninstalled',
                                index == 0, 'catalogue-%s' % index])
                cursor.execute('SELECT * FROM ir_module_module ORDER BY id')
                snapshots[name] = cursor.fetchall()
        assert len(set(identities)) == 2
        manifests = {'base': {'depends': [], 'installable': True},
                     'physical_child': {'depends': ['base'], 'installable': True}}
        native = ModuleGraph._update_from_database

        def wrong_alias(graph, added, *, using):
            return native(graph, added, using=names[0])

        with mock.patch('modules.module_graph.load_manifest', manifests.__getitem__), \
                mock.patch.object(ModuleGraph, '_update_from_database',
                                  wrong_alias if '--wrong-alias' in sys.argv else native):
            first = ModuleGraph.from_database(['base'], using=names[0])
            second = ModuleGraph.from_database(['base'], using=names[1])
            first['base'].state = 'to upgrade'
            first.extend(['physical_child'])
            second.extend(['physical_child'])
            assert 'physical_child' in first
            assert 'physical_child' not in second, 'Wrong physical catalogue admitted an uninstalled child'
            assert first['physical_child'].id == 1001
            assert first['physical_child'].demo is True
            assert first['physical_child'].load_version == 'catalogue-0'
            assert second['base'].id == 2000
            assert second['base'].demo is False
            assert second['base'].load_version == 'catalogue-1'
            assert (first['base'].state, first['base'].load_state) == ('to upgrade', 'installed')
        for name in names:
            with connections[name].cursor() as cursor:
                cursor.execute('SELECT * FROM ir_module_module ORDER BY id')
                assert cursor.fetchall() == snapshots[name]
        result.update(physical_identities=identities, catalogue_unchanged=True,
                      existing_snapshot_preserved=True, result='PASS')
except Exception as exc:
    error = exc
    result.update(result='FAIL', error_type=type(exc).__name__, error=str(exc))
finally:
    remaining = [name for name in names if svc.database_exists(name)]
    result['remaining_owned_candidates'] = remaining
    if hba:
        subprocess.run(['docker', 'exec', '-u', 'postgres', container, 'sh', '-c',
                        f"sed -i '/# {marker}$/d' \"$PGDATA/pg_hba.conf\""], check=True)
        admin('SELECT pg_reload_conf();')
    connections['default'].close()
    result['cleanup'] = 'PASS' if not remaining else 'FAIL'
    (output / ('physical-catalogue-' + mode + '.json')).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
if error is not None or result['cleanup'] != 'PASS':
    raise SystemExit(1)
