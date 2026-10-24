"""Observa sólo metadatos de las bases del rol efímero declarado."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

role = sys.argv[1]
assert re.fullmatch(r'orm_bootstrap_[0-9a-f]{12}', role)
container = os.environ['ORM_QA_CONTAINER']


def query(database, sql):
    return subprocess.check_output(['docker', 'exec', '-u', 'postgres', container,
        'psql', '-X', '-t', '-A', '-v', 'ON_ERROR_STOP=1', '-d', database,
        '-c', sql], text=True).strip()


names = query('postgres', f"SELECT datname FROM pg_database WHERE pg_get_userbyid(datdba)='{role}' ORDER BY datname").splitlines()
rows = []
for name in names:
    assert name == role or re.fullmatch(r'company_\d+_db', name)
    migrations = None
    if query(name, "SELECT to_regclass('django_migrations')"):
        migrations = int(query(name, 'SELECT count(*) FROM django_migrations'))
    user_keys = int(query(name, "SELECT count(*) FROM pg_constraint c JOIN pg_class p ON p.oid=c.confrelid WHERE c.contype='f' AND p.relname='res_users'"))
    rows.append({'database': name, 'applied_migrations': migrations, 'local_res_users_foreign_keys': user_keys})
result = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'instrument_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'owner_role': role, 'schema_observations': rows,
          'limit': 'Concurrent read-only schema snapshot; not test or TASK acceptance'}
filename = 'current-isolation-schema-observations.jsonl' if '--current-run' in sys.argv else 'isolation-schema-observations.jsonl'
with (Path(__file__).resolve().parents[1] / 'outputs' / filename).open('a') as stream:
    stream.write(json.dumps(result) + '\n')
print(json.dumps(result, indent=2))
