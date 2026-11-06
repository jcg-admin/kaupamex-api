"""Ejecuta test_multidb_isolation sobre una base desechable propia.

La base se crea con un nombre impredecible ``orm_bootstrap_<hex>`` que no
existía antes de la ejecución; su propiedad la prueba ``pg_database`` (dueño:
el rol exclusivo de esta VM, con CREATEDB). El guard del fixture no se toca:
se le entrega lo que exige (prefijo admitido y ``CI_DATABASE_DISPOSABLE`` con
el nombre exacto). Al terminar se elimina sólo esa base, y se comprueba que
las bases ``company_*`` que crea la prueba ya no existen.

No imprime credenciales: las lee de ``src/.env`` por ``decouple`` y sólo las
pasa al entorno de los subprocesos.

Uso: run_isolation_on_disposable_database.py <directorio-salida>
"""
import json
import os
import pathlib
import platform
import secrets
import subprocess
import sys
import time

import psycopg
from decouple import Config, RepositoryEnv

ROOT = pathlib.Path(__file__).resolve().parents[3]
TEST = 'tests/integration/company/test_multidb_isolation.py'
#: Crear la base de prueba y aprovisionar dos bases de empresa con todas
#: las migraciones superó 20 min en la primera ejecución (la segunda
#: prueba seguía aprovisionando cuando se cortó).
PYTEST_BUDGET = 3 * 3600


def connect(env, dbname='postgres'):
    return psycopg.connect(
        host=env['DB_QA_HOST'] or None, port=env['DB_QA_PORT'] or None,
        user=env['DB_QA_USER'], password=env['DB_QA_PASSWORD'],
        dbname=dbname, autocommit=True)


def catalog(env, name):
    """Dueño de ``name`` y las bases ``company_*`` presentes."""
    with connect(env) as conn:
        owner = conn.execute(
            'SELECT pg_get_userbyid(datdba) FROM pg_database'
            ' WHERE datname = %s',
            [name]).fetchone()
        companies = [row[0] for row in conn.execute(
            "SELECT datname FROM pg_database WHERE datname LIKE 'company\\_%'"
            ' ORDER BY datname')]
        server = conn.execute('SHOW server_version').fetchone()[0]
        role = conn.execute(
            'SELECT current_user, rolcreatedb FROM pg_roles'
            ' WHERE rolname = current_user').fetchone()
    return (owner[0] if owner else None), companies, server, role


def run(command, env, log, budget=None):
    """El código de salida, o ``'timeout'`` si el presupuesto se agota."""
    with open(log, 'w') as out:
        try:
            return subprocess.run(command, cwd=ROOT, env=env, stdout=out,
                                  stderr=subprocess.STDOUT,
                                  timeout=budget).returncode
        except subprocess.TimeoutExpired:
            return 'timeout'


def drop_created(env, name, companies_before):
    """Elimina ``name`` y las ``company_*`` que aparecieron en esta ejecución.

    Una prueba interrumpida no ejecuta su propia limpieza; las bases que no
    existían antes de la ejecución y son del rol exclusivo son las suyas.
    """
    owner, companies, _, _ = catalog(env, name)
    created = [c for c in companies if c not in companies_before]
    with connect(env) as conn:
        for database in [name] * (owner is not None) + created:
            found = conn.execute(
                'SELECT pg_get_userbyid(datdba) FROM pg_database'
                ' WHERE datname = %s', [database]).fetchone()
            assert found and found[0] == env['DB_QA_USER'], database
            conn.execute(f'DROP DATABASE "{database}" WITH (FORCE)')
    return created


def main(out_dir):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    source = Config(RepositoryEnv(str(ROOT / 'src' / '.env')))
    keys = ('USER', 'PASSWORD', 'HOST', 'PORT', 'SSL_MODE', 'SOCKET')
    name = 'orm_bootstrap_' + secrets.token_hex(6)
    env = dict(os.environ)
    for key in keys:
        env['DB_QA_' + key] = source('DB_QA_' + key, default='')
        env['DB_' + key] = env['DB_QA_' + key]
    env.update(DB_QA_NAME=name, DB_NAME=name, CI_DATABASE_DISPOSABLE=name,
               DJANGO_SETTINGS_MODULE='config.settings.testing',
               PYTHONPATH='src')
    record = {'database': name}

    owner, companies_before, server, role = catalog(env, name)
    assert owner is None, f'{name} ya existía: no se reutiliza'
    record.update(existed_before=False, companies_before=companies_before,
                  postgresql=server, role=role[0], role_createdb=role[1])

    guard = run([sys.executable, 'scripts/check_ci_database.py'], env,
                out / 'check_ci_database.log')
    record['check_ci_database_exit'] = guard
    if guard != 0:
        print(json.dumps(record, indent=1))
        return 2

    started = time.monotonic()
    try:
        pytest_exit = run(
            [sys.executable, '-m', 'pytest', TEST, '--create-db', '-v',
             '-p', 'no:cacheprovider',
             f'--junitxml={out / "junit_isolation.xml"}'],
            env, out / 'pytest_isolation.log', budget=PYTEST_BUDGET)
        record['pytest_exit'] = pytest_exit
        record['pytest_seconds'] = round(time.monotonic() - started)
        owner, companies_after, _, _ = catalog(env, name)
        record.update(owner_after=owner, companies_after=companies_after)
    finally:
        record['dropped_companies'] = drop_created(env, name,
                                                   companies_before)
        owner, companies_left, _, _ = catalog(env, name)
        record['dropped'] = owner is None
        record['companies_left'] = companies_left
    versions = subprocess.run(
        [sys.executable, '-c',
         'import django, psycopg, pytest; '
         'print(django.get_version(), psycopg.__version__,'
         ' pytest.__version__)'],
        cwd=ROOT, env=env, capture_output=True, text=True).stdout.split()
    record.update(python=platform.python_version(), django=versions[0],
                  psycopg=versions[1], pytest=versions[2],
                  command=f'pytest {TEST} --create-db -v')
    (out / 'record.json').write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps(record, indent=1))
    return 0 if pytest_exit == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
