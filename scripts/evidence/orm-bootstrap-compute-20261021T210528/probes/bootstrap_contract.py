"""Prueba del flujo Django migrate real en una base nueva y exclusivamente propia."""
import json
import sys
from pathlib import Path
import django
from django.conf import settings
from django.core.management import call_command
from django.db import connection

if '--without-testorm-migration' in sys.argv:
    settings.MIGRATION_MODULES = {**getattr(settings, 'MIGRATION_MODULES', {}), 'test_orm': None}
django.setup()
try:
    call_command('migrate', run_syncdb=True, interactive=False, verbosity=1)
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('res_users'),to_regclass('test_orm_testormdiscussion')")
        tables = cursor.fetchone()
        assert all(tables), tables
        cursor.execute("SELECT conname,convalidated FROM pg_constraint WHERE conrelid='test_orm_testormdiscussion'::regclass AND confrelid='res_users'::regclass")
        constraints = cursor.fetchall()
        assert constraints and all(row[1] for row in constraints), constraints
        print(json.dumps({'tables': tables, 'foreign_keys': constraints}))
    call_command('migrate', run_syncdb=True, interactive=False, verbosity=0)
    print('PASS repeated native migrate and validated res_users foreign key')
finally:
    connection.close()
