"""Compatibilidad de la migración inicial con tablas legacy, sólo en fixture propia."""
import json
import django
from django.core.management import call_command
from django.core.management.commands.migrate import Command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

django.setup()
MigrationExecutor(connection).migrate([('base', '0001_initial')])
# Reproduce la antigua ruta de creación, con la dependencia ya materializada.
command = Command()
command.verbosity = 0
command.sync_apps(connection, ['test_orm'])
with connection.cursor() as cursor:
    cursor.execute("""INSERT INTO test_orm_testormcategory
        (id,created_at,updated_at,name,color,parent_path,parent_id)
        VALUES(918273,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'Legacy category',0,'918273/',918273)""")


def catalog():
    with connection.cursor() as cursor:
        cursor.execute("""SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull
            FROM pg_attribute a JOIN pg_class c ON a.attrelid=c.oid
            WHERE c.relname LIKE 'test_orm_%' AND a.attnum>0 AND NOT a.attisdropped
            ORDER BY c.relname,a.attnum""")
        columns = cursor.fetchall()
        cursor.execute("""SELECT c.relname,pg_get_constraintdef(k.oid),k.convalidated
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            WHERE c.relname LIKE 'test_orm_%' ORDER BY c.relname,pg_get_constraintdef(k.oid)""")
        constraints = cursor.fetchall()
    return columns, constraints


before = catalog()
MigrationExecutor(connection).migrate([('test_orm', '0001_initial')], fake_initial=True)
assert catalog() == before
with connection.cursor() as cursor:
    cursor.execute('SELECT name FROM test_orm_testormcategory WHERE id=918273')
    assert cursor.fetchone() == ('Legacy category',)
    cursor.execute("SELECT count(*) FROM django_migrations WHERE app='test_orm' AND name='0001_initial'")
    assert cursor.fetchone() == (1,)
call_command('makemigrations', 'test_orm', check_changes=True, dry_run=True, verbosity=1)
print(json.dumps({'legacy_initial_adoption': 'PASS', 'columns_and_constraints_unchanged': True,
                  'sentinel_row_preserved': True, 'migration_recorded': True,
                  'limits': 'Native --fake-initial only for verified matching legacy schema; no shared database touched.'}))
connection.close()
