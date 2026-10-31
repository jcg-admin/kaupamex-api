"""Verifica el fixture Consumer con PostgreSQL propio, sin coordinar TASK."""
import importlib.util
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
from unittest import mock

import django

django.setup()

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from service import db as svc

root = Path.cwd()
output = Path(__file__).resolve().parents[1] / 'outputs'
artifact_prefix = 'current-isolation' if '--reuse-current-ci' in sys.argv else 'isolation'
name = settings.DATABASES['default']['NAME']
role = settings.DATABASES['default']['USER']
assert re.fullmatch(r'orm_bootstrap_[0-9a-f]{12}', name) and role == name
os.environ['CI_DATABASE_DISPOSABLE'] = name
settings.MULTIDB_MANAGEMENT_ENABLED = True
container = os.environ['ORM_QA_CONTAINER']
marker = name + '_isolation'
results = {'task': 'TASK-API-0383', 'source_revision': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], text=True).strip(), 'acceptance': 'not_verified',
    'scope': 'Fixture qualification and data isolation, not whole authentication or loader acceptance'}


def admin(sql):
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                   input=sql, text=True, check=True)


path = root / 'tests/integration/company/test_multidb_isolation.py'
spec = importlib.util.spec_from_file_location('qualified_isolation_fixture', path)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
alias = 'company_' + str(secrets.randbits(48)) + '_db'
created = hba = False
try:
    admin(f'ALTER ROLE {role} CREATEDB;')
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'], input=
                   f'\nhost all {role} {os.environ["ORM_QA_BRIDGE"]}/32 scram-sha-256 # {marker}\n',
                   text=True, check=True)
    hba = True
    admin('SELECT pg_reload_conf();')
    if '--reuse-current-ci' in sys.argv:
        prior = json.loads((output / 'incremental-graph-summary.json').read_text())['verification']['mandatory_ci']
        # Reutilizar el gate exige las mismas fuentes, pruebas y configuración.
        subprocess.run(['git', 'diff', '--quiet', prior['revision'], 'HEAD', '--',
                        'src', 'addons', 'tests', 'Makefile', 'pytest.ini',
                        'pyproject.toml', 'uv.lock', 'scripts/check_ci_database.py',
                        '.github/workflows/api-tests.yml'], check=True)
        assert prior['make_exit'] == 2 and prior['classification'] == 'BASELINE_FAILURE'
        results['ci_make_exit'] = prior['make_exit']
        results['ci_reused_revision'] = prior['revision']
        results['ci_reused_evidence'] = 'incremental-graph-ci.junit.xml; incremental-graph-ci.log; production/tests/gate unchanged'
        print('Reuse unchanged-source CI baseline failure; prepare own schema for current fixture qualification', flush=True)
        call_command('migrate', database='default', run_syncdb=True, verbosity=0)
    elif '--bounded-only' in sys.argv:
        prior = json.loads((output / 'isolation-qualification-initial.json').read_text())
        assert prior['source_revision'] == results['source_revision']
        assert prior['ci_make_exit'] == 2
        results['ci_make_exit'] = prior['ci_make_exit']
        results['ci_reused_evidence'] = 'isolation-ci.junit.xml; isolation-ci-and-functional.log; no repeated CI run'
        print('Begin fresh disposable default schema for bounded verification only', flush=True)
        call_command('migrate', database='default', run_syncdb=True, verbosity=0)
        print('Fresh default schema ready; begin owned-resource controls', flush=True)
    else:
        results['ci_make_exit'] = subprocess.run(['make', 'ci-verify']).returncode
        junit = root / 'test-results/pytest.xml'
        if junit.exists():
            (output / (artifact_prefix + '-ci.junit.xml')).write_bytes(junit.read_bytes())
    svc.create_empty_database(alias)
    created = True
    svc.install_company_aliases(settings.DATABASES, [alias])
    with connections[alias].cursor() as cursor:
        cursor.execute('CREATE TABLE ownership_sentinel (value integer)')
        cursor.execute('INSERT INTO ownership_sentinel VALUES (42)')
    fixture._forget_alias(alias)
    try:
        with fixture._company_databases((alias,)):
            raise AssertionError('Preexisting database was acquired')
    except RuntimeError as error:
        assert 'existing' in str(error)
    svc.install_company_aliases(settings.DATABASES, [alias])
    with connections[alias].cursor() as cursor:
        cursor.execute('SELECT value FROM ownership_sentinel')
        assert cursor.fetchall() == [(42,)]
    svc.drop_database(alias)
    created = False
    fixture._forget_alias(alias)
    results['preexisting_database_and_sentinel_preserved'] = True

    def fail_after_partial_schema(target):
        with connections[target].cursor() as cursor:
            cursor.execute('CREATE TABLE partial_owned_schema (value integer)')
        raise RuntimeError('Injected migration failure after actual DDL')

    with mock.patch.object(svc, 'provision_company_database', side_effect=fail_after_partial_schema):
        try:
            with fixture._company_databases((alias,)):
                raise AssertionError('Partial migration unexpectedly succeeded')
        except RuntimeError as error:
            assert 'actual DDL' in str(error)
    assert not svc.database_exists(alias) and alias not in settings.DATABASES
    results['partial_schema_failure_cleaned_own_database'] = True
    # El servicio registra fallos de extensiones sin perder el recurso adquirido.
    original_connect = svc._connect

    def fail_extension_connection(database, using='default'):
        if database == alias:
            raise RuntimeError('Injected extension connection failure')
        return original_connect(database, using)

    with mock.patch.object(svc, '_connect', side_effect=fail_extension_connection):
        svc.create_empty_database(alias)
    created = True
    assert svc.database_exists(alias)
    svc.drop_database(alias)
    created = False
    results['extension_failure_retains_owned_database_for_cleanup'] = True
    print('Real resource safety controls PASS; begin five isolation cases', flush=True)
    results['isolation_pytest_exit'] = int(pytest.main([
        str(path), '--confcutdir=' + str(path.parent), '-vv', '-s',
        '-o', 'addopts=', '--junitxml=' + str(output / (artifact_prefix + '-functional.junit.xml'))]))
    results['qualification_limit'] = 'No root conftest seed replay in bounded run; native provisioner applies all migrations. Full CI measured separately above.'
    results['aliases_after_teardown'] = [alias for alias in settings.DATABASES if alias.startswith('company_')]
    assert not results['aliases_after_teardown']
    # pytest restaura su blocker; el cierre de infraestructura usa mantenimiento.
    sql = ("SELECT coalesce(json_agg(datname), '[]'::json) FROM pg_database "
           f"WHERE pg_get_userbyid(datdba)='{role}' AND datname != '{name}'")
    payload = subprocess.check_output(['docker', 'exec', '-u', 'postgres', container,
        'psql', '-X', '-t', '-A', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres', '-c', sql], text=True)
    results['owned_extra_databases_after_teardown'] = json.loads(payload)
    assert not results['owned_extra_databases_after_teardown']
finally:
    if created:
        svc.drop_database(alias)
    if alias in settings.DATABASES:
        fixture._forget_alias(alias)
    if hba:
        subprocess.run(['docker', 'exec', '-u', 'postgres', container, 'sh', '-c',
                        f'sed -i "/# {marker}$/d" "$PGDATA/pg_hba.conf"'], check=True)
        admin('SELECT pg_reload_conf();')
    (output / (artifact_prefix + '-qualification.json')).write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2), flush=True)
raise SystemExit(results['isolation_pytest_exit'] if '--bounded-only' in sys.argv or '--reuse-current-ci' in sys.argv else results['ci_make_exit'] or results['isolation_pytest_exit'])
