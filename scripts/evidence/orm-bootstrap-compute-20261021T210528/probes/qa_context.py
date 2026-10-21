"""Recurso PostgreSQL aislado para verificar el bootstrap Consumer, nunca QA compartida."""
import os
import secrets
import subprocess
import sys
from pathlib import Path

root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
container = os.environ['ORM_QA_CONTAINER']
host = os.environ['ORM_QA_HOST']
bridge = os.environ['ORM_QA_BRIDGE']
identifier = 'orm_bootstrap_' + secrets.token_hex(6)
password = secrets.token_hex(32)


def admin(sql):
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                   input=sql, text=True, check=True)


admin(f"CREATE ROLE {identifier} LOGIN PASSWORD '{password}';")
created = added = False
try:
    admin(f'CREATE DATABASE {identifier} OWNER {identifier};')
    created = True
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'],
                   input=f'\nhost {identifier},postgres {identifier} {bridge}/32 scram-sha-256 # {identifier}\n',
                   text=True, check=True)
    added = True
    admin('SELECT pg_reload_conf();')
    env = dict(os.environ)
    env.update(SECRET_KEY=secrets.token_urlsafe(50),
               DJANGO_SETTINGS_MODULE='config.settings.testing',
               PYTHONPATH=str(root/'src'), UV_CACHE_DIR=str(root.parent/'.cache/uv'))
    env.pop('PGOPTIONS', None)
    for prefix in ('DB_', 'DB_QA_'):
        env.update({prefix+'NAME': identifier, prefix+'USER': identifier,
                    prefix+'PASSWORD': password, prefix+'HOST': host,
                    prefix+'PORT': '5432', prefix+'SSL_MODE': 'disable', prefix+'SOCKET': ''})
    result = subprocess.run(sys.argv[1:], cwd=root, env=env)
finally:
    if added:
        subprocess.run(['docker', 'exec', '-u', 'postgres', container, 'sh', '-c',
                        f"sed -i '/# {identifier}$/d' \"$PGDATA/pg_hba.conf\""], check=True)
        admin('SELECT pg_reload_conf();')
    if created:
        # Sólo el nombre impredecible creado arriba, tras terminar el subproceso.
        admin(f'DROP DATABASE {identifier};')
    admin(f'DROP ROLE {identifier};')
raise SystemExit(result.returncode)
