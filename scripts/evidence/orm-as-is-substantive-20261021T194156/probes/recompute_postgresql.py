"""Verificador Consumer de recálculo sobre PostgreSQL QA con rol temporal."""
import ast
import importlib
import sys
import os
import secrets
import subprocess
import unittest
import django
from django.conf import settings
from django.db import connections
container=os.environ['ORM_QA_CONTAINER']
database=os.environ['ORM_QA_DATABASE']
host=os.environ['ORM_QA_HOST']
bridge=os.environ['ORM_QA_BRIDGE']
assert database=='kaupamex_core_qa'
def admin(sql):
    result = subprocess.run(
        ['docker', 'exec', '-i', '-u', 'postgres', container,
         'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', database],
        input=sql, text=True, capture_output=True, check=True,
    )
    print(result.stdout, end='')


role = 'missing_contract_' + secrets.token_hex(6)
password = secrets.token_hex(32)
admin(f"CREATE ROLE {role} LOGIN PASSWORD '{password}';\n"
      f'GRANT CONNECT,TEMP ON DATABASE {database} TO {role};')
hba_added = False
try:
    # Misma red local de la regla existente de django_user, sólo QA y este
    # rol efímero. SCRAM se mantiene; no se usa trust ni se cambia otro rol.
    subprocess.run(
        ['docker', 'exec', '-i', '-u', 'postgres', container,
         'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'],
        input=f'\nhost {database} {role} {bridge}/32 scram-sha-256 # {role}\n',
        text=True, check=True,
    )
    hba_added = True
    admin('SELECT pg_reload_conf();')
    settings.configure(
        INSTALLED_APPS=['django.contrib.contenttypes'],
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        DATABASES={'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': database, 'USER': role, 'PASSWORD': password,
            'HOST': host, 'PORT': '5432', 'OPTIONS': {'sslmode': 'disable'},
        }},
    )
    django.setup()
    module = importlib.import_module('orm.models')
    if '--baseline' in sys.argv:
        source = subprocess.check_output(['git','show','35501644c380f5f198e407fee16357994ac43b27:src/orm/models.py'],text=True)
        node = next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='_recompute_field')
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<baseline recompute>','exec'),module.__dict__)
        print('Negative control: original _recompute_field restored in memory only')
    if '--retry-baseline' in sys.argv:
        source = subprocess.check_output(['git','show','99f4a0445c163b8a5228e3df68121ce27905559b:src/orm/fields.py'],text=True)
        node = next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='recompute')
        field_module = importlib.import_module('orm.fields')
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<baseline retry>','exec'),field_module.__dict__)
        field_module.models.Field.recompute = field_module.recompute
        print('Negative control: original Field.recompute restored in memory only')
    if '--without-record-alias' in sys.argv:
        field_module=importlib.import_module('orm.fields')
        node=next(n for n in ast.parse(open(field_module.__file__).read()).body if isinstance(n,ast.FunctionDef) and n.name=='recompute')
        body=ast.unparse(node)
        assert body.count('._base_manager.using(record._state.db)')==1
        body=body.replace('._base_manager.using(record._state.db)','._base_manager')
        exec(compile(body,'<without record alias>','exec'),field_module.__dict__)
        field_module.models.Field.recompute=field_module.recompute
        print('Negative control: removed only record DB alias binding in memory')
    pattern = ('test_relational_reconstruction_persistence.py' if '--relations-only' in sys.argv
               else 'test_missing_recompute.py')
    suite = unittest.defaultTestLoader.discover('tests/unit/orm', pattern=pattern)
    if '--retry-only' in sys.argv:
        suite = unittest.TestSuite(test for group in suite for nested in group for test in nested
                                   if test._testMethodName.startswith('test_retry_'))
    if '--alias-only' in sys.argv:
        suite=unittest.TestSuite(test for group in suite for nested in group for test in nested
                                if test._testMethodName=='test_retry_uses_record_database_instead_of_read_router')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    success = result.wasSuccessful()
finally:
    connections.close_all()
    if hba_added:
        subprocess.run(['docker','exec','-u','postgres',container,'sh','-c',f"sed -i '/# {role}$/d' \"$PGDATA/pg_hba.conf\""], check=True)
        admin('SELECT pg_reload_conf();')
    admin(f'REVOKE CONNECT,TEMP ON DATABASE {database} FROM {role};\nDROP ROLE {role};')
raise SystemExit(0 if success else 1)
