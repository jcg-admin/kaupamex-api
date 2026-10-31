"""Verifica tablas históricas sobre un recurso PostgreSQL desechable propio."""
import copy
import os
import sys
import django

django.setup()
from django.conf import settings
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from service.db import DatabaseSchemaIncomplete, _check_applied_schema

assert os.environ['DB_QA_NAME'].startswith('orm_bootstrap_')
if '--router-exclusion' in sys.argv:
    alias = 'company_0123456789_db'
    settings.DATABASES[alias] = copy.deepcopy(settings.DATABASES['default'])
    connections.databases[alias] = settings.DATABASES[alias]
    target_connection = connections[alias]
    MigrationExecutor(target_connection).migrate([('sessions', '0001_initial')])
    with target_connection.cursor() as cursor:
        assert 'django_session' not in target_connection.introspection.table_names(cursor)
        cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'sessions'")
        assert cursor.fetchone() == (1,)
    _check_applied_schema(alias)
    target_connection.close()
    print('PASS: exclusión real del router no produce falso positivo')
    raise SystemExit(0)
if '--annul' in sys.argv:
    _check_applied_schema = lambda alias: None
executor = MigrationExecutor(connection)
relation = '--relations' in sys.argv
target = ('auth', '0001_initial') if relation else ('contenttypes', '0001_initial')
missing_table = 'auth_group_permissions' if relation else 'django_content_type'
executor.migrate([target])
_check_applied_schema('default')
print('PASS: historial parcial válido; tablas pendientes no exigidas')
with connection.cursor() as cursor:
    cursor.execute('SELECT app, name FROM django_migrations ORDER BY app, name')
    before = cursor.fetchall()
    cursor.execute('CREATE TABLE preflight_sentinel (value integer)')
    cursor.execute('INSERT INTO preflight_sentinel VALUES (42)')
    cursor.execute('DROP TABLE ' + connection.ops.quote_name(missing_table))
try:
    _check_applied_schema('default')
except DatabaseSchemaIncomplete as exc:
    assert missing_table in str(exc)
    print('PASS: tabla histórica ausente rechazada')
else:
    raise AssertionError('El detector admitió una tabla histórica ausente')
with connection.cursor() as cursor:
    cursor.execute('SELECT app, name FROM django_migrations ORDER BY app, name')
    assert cursor.fetchall() == before
    cursor.execute('SELECT value FROM preflight_sentinel')
    assert cursor.fetchall() == [(42,)]
print('PASS: historial y datos ajenos preservados; sin reparación')
connection.close()
