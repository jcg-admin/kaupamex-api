"""Verifica TASK-API-0420 con modelos Django y rol QA temporal mínimo.

No carga addons completos ni aplica migraciones productivas. Crea un rol
efímero con CONNECT/TEMP en QA y lo elimina al cerrar todas las conexiones.
La contraseña aleatoria sólo se transmite por stdin al canal administrativo.
"""
import secrets
import subprocess
import unittest

import django
from django.conf import settings
from django.db import connection, connections
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.questioner import MigrationQuestioner
from django.db.migrations.state import ModelState, ProjectState
from django.db.migrations.writer import MigrationWriter


def admin(sql):
    result = subprocess.run(
        ['docker', 'exec', '-i', '-u', 'postgres', 'kaupamex-postgres-cloud',
         'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', 'kaupamex_core_qa'],
        input=sql, text=True, capture_output=True, check=True,
    )
    print(result.stdout, end='')


role = 'json_contract_' + secrets.token_hex(6)
password = secrets.token_hex(32)
admin(f"CREATE ROLE {role} LOGIN PASSWORD '{password}';\n"
      f'GRANT CONNECT,TEMP ON DATABASE kaupamex_core_qa TO {role};')
hba_added = False
try:
    # Misma red local de la regla existente de django_user, sólo QA y este
    # rol efímero. SCRAM se mantiene; no se usa trust ni se cambia otro rol.
    subprocess.run(
        ['docker', 'exec', '-i', '-u', 'postgres', 'kaupamex-postgres-cloud',
         'sh', '-c', 'cat >> "$PGDATA/pg_hba.conf"'],
        input=f'\nhost kaupamex_core_qa {role} 172.17.0.1/32 scram-sha-256 # {role}\n',
        text=True, check=True,
    )
    hba_added = True
    admin('SELECT pg_reload_conf();')
    settings.configure(
        INSTALLED_APPS=['django.contrib.contenttypes'],
        DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        DATABASES={'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'kaupamex_core_qa', 'USER': role, 'PASSWORD': password,
            'HOST': '127.0.0.1', 'PORT': '5432', 'OPTIONS': {'sslmode': 'disable'},
        }},
    )
    django.setup()
    suite = unittest.defaultTestLoader.discover(
        'tests/unit/orm', pattern='test_json_defaults.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful(), 'Django unit contracts failed'
    # El módulo ya fue cargado por unittest; no se sustituye su modelo.
    model = __import__('test_json_defaults').JsonDefaultModel
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_user, current_database(), '
                       '(SELECT rolsuper FROM pg_roles WHERE rolname=current_user)')
        user, database, superuser = cursor.fetchone()
        assert user == role and database == 'kaupamex_core_qa' and not superuser
    with connection.schema_editor(collect_sql=True) as editor:
        editor.create_model(model)
    with connection.cursor() as cursor:
        for sql in editor.collected_sql:
            assert sql.startswith('CREATE TABLE '), sql
            cursor.execute(sql.replace('CREATE TABLE ', 'CREATE TEMP TABLE ', 1))
    first, second = model(), model()
    first.history['delete_messages'].append('first-only')
    first.save(force_insert=True)
    second.save(force_insert=True)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.history == {'delete_messages': ['first-only']}
    assert second.history == {'delete_messages': []}
    second.history = {'delete_messages': ['second-only']}
    second.save(update_fields=['history'])
    first.refresh_from_db()
    assert first.history == {'delete_messages': ['first-only']}
    assert model().history == {'delete_messages': []}
    before = ProjectState()
    state = ModelState.from_model(model)
    # Estado controlado de migración: managed=False impediría detectar incluso
    # una alteración incorrecta y produciría un verde sin discriminación.
    state.options['managed'] = True
    before.add_model(state)
    after = before.clone()
    serialized, imports = MigrationWriter.serialize(model._meta.get_field('history'))
    namespace = {}
    for statement in imports:
        exec(statement, namespace)
    restored = eval(serialized, namespace)
    key = (model._meta.app_label, model._meta.model_name)
    after.models[key].fields['history'] = restored
    changes = MigrationAutodetector(
        before, after, MigrationQuestioner({'ask_initial': False})
    )._detect_changes()
    assert changes == {}, changes
    negative = after.clone()
    bad_field = restored.clone()
    bad_field.default = dict
    negative.models[key].fields['history'] = bad_field
    rejected = MigrationAutodetector(
        before, negative, MigrationQuestioner({'ask_initial': False})
    )._detect_changes()
    assert rejected, 'Migration control did not detect lost default content'
    print('PASS: real Django model save/read/update, JSONB, non-superuser QA role, '
          'serialized migration-state equality and changed-default negative control')
finally:
    connections.close_all()
    if hba_added:
        subprocess.run(
            ['docker', 'exec', '-u', 'postgres', 'kaupamex-postgres-cloud',
             'sh', '-c', f"sed -i '/# {role}$/d' \"$PGDATA/pg_hba.conf\""],
            check=True,
        )
        admin('SELECT pg_reload_conf();')
    admin(f'REVOKE CONNECT,TEMP ON DATABASE kaupamex_core_qa FROM {role};\n'
          f'DROP ROLE {role};')
