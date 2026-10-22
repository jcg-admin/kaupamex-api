"""Control del ciclo de conexión en DDL de fixture con un entorno sin actor vivo."""
import json
import sys
import django
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

django.setup()
from orm.environments import env

MigrationExecutor(connection).migrate([('base', '0001_initial')])
# Retener el entorno fuerza la precondición del traceback de cierre de fixture.
live_environment = env()
if '--close-boundary' in sys.argv:
    connection.close()
try:
    with connection.schema_editor() as editor:
        editor.execute('CREATE TEMP TABLE fixture_boundary_probe (id integer)')
    print(json.dumps({'result': 'PASS', 'connection_boundary': '--close-boundary' in sys.argv,
                      'no_public_actor_or_permissions_changed': True}))
finally:
    connection.close()
