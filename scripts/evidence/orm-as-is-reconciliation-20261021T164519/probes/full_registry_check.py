"""Comprobación de registro tras unidad acotada TASK-GEN-0559, sin migrar o cambiar datos QA.

El contenedor, base y dirección se declaran por parámetros de esta sonda.
El rol efímero sólo puede conectar; no sustituye el aprovisionamiento real.
"""
import json
import os
import secrets
import subprocess
from pathlib import Path


root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
out = Path(__file__).resolve().parents[1] / 'outputs'
container = os.environ['ORM_QA_CONTAINER']
database = os.environ['ORM_QA_DATABASE']
host = os.environ['ORM_QA_HOST']
bridge = os.environ['ORM_QA_BRIDGE']
assert database == 'kaupamex_core_qa', 'Esta prueba sólo admite la QA conocida'
role = 'relation_check_' + secrets.token_hex(6)
password = secrets.token_hex(32)


def admin(sql):
    return subprocess.run(
        ['docker', 'exec', '-i', '-u', 'postgres', container, 'psql',
         '-X', '-v', 'ON_ERROR_STOP=1', '-d', database],
        input=sql, text=True, capture_output=True, check=True,
    )


admin(f"CREATE ROLE {role} LOGIN PASSWORD '{password}';\n"
      f'GRANT CONNECT ON DATABASE {database} TO {role};')
added = False
results = []
try:
    subprocess.run(['docker', 'exec', '-i', '-u', 'postgres', container,
                    'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'],
                   input=f'\nhost {database} {role} {bridge}/32 scram-sha-256 # {role}\n',
                   text=True, check=True)
    added = True
    admin('SELECT pg_reload_conf();')
    env = dict(os.environ)
    env.update(SECRET_KEY=secrets.token_urlsafe(50),
               DJANGO_SETTINGS_MODULE='config.settings.testing',
               PYTHONPATH=str(root / 'src'),
               PGOPTIONS='-c default_transaction_read_only=on')
    for prefix in ('DB_', 'DB_QA_'):
        env.update({prefix+'NAME': database, prefix+'USER': role,
                    prefix+'PASSWORD': password, prefix+'HOST': host,
                    prefix+'PORT': '5432', prefix+'SSL_MODE': 'disable',
                    prefix+'SOCKET': ''})
    for label, args in [('django-check', ['check'])]:
        command = ['uv', 'run', '--frozen', 'python', 'src/manage.py', *args]
        result = subprocess.run(command, cwd=root, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # El subproceso no imprime las variables ni sus credenciales.
        text = result.stdout.replace(password, '<redacted>').replace(env['SECRET_KEY'], '<redacted>')
        (out / (label + '.log')).write_text(text)
        row = {'command': command, 'exit_code': result.returncode,
               'log': label+'.log', 'json_e010_reported': 'fields.E010' in text}
        results.append(row)
        print(json.dumps(row))
        print('\n'.join(text.splitlines()[:8]))
finally:
    if added:
        subprocess.run(['docker', 'exec', '-u', 'postgres', container, 'sh', '-c',
                        f"sed -i '/# {role}$/d' \"$PGDATA/pg_hba.conf\""], check=True)
        admin('SELECT pg_reload_conf();')
    admin(f'REVOKE CONNECT ON DATABASE {database} FROM {role};\nDROP ROLE {role};')

(out / 'management-results.json').write_text(json.dumps({
    'consumer_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'read_only_database_session': True, 'results': results,
    'limits': 'Normal installed addons/checks; no migrations applied, no fixtures seeded, no whole-ORM acceptance',
}, indent=2) + '\n')
raise SystemExit(0 if all(row['exit_code'] == 0 for row in results) else 1)
