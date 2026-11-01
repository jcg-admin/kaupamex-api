"""Verify class-declared virtual relation deletion on owned PostgreSQL.

The terminal supplies the disposable server. Only temporary fixture tables
are created, without application migrations or shared resource mutations.
"""

import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import django
from django.apps import apps
from django.core.exceptions import FieldError
from django.db import connection, models, transaction

JOB = Path(__file__).resolve().parents[1]
SOURCE = 'src/orm/fields_relational.py'
MODULE = 'orm.fields_relational'


class RelationalSnapshot(importlib.abc.MetaPathFinder):
    def __init__(self, source):
        self.source = source

    def find_spec(self, fullname, path=None, target=None):
        if fullname == MODULE:
            return importlib.util.spec_from_file_location(
                fullname, self.source
            )
        return None


def main():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        for key, value in {
            'NAME': 'postgres', 'USER': 'postgres',
            'PASSWORD': os.environ['ORM_DELETE_PASSWORD'],
            'HOST': '127.0.0.1', 'PORT': os.environ['ORM_DELETE_PORT'],
            'SSL_MODE': 'disable', 'SOCKET': '',
        }.items():
            os.environ[prefix + key] = value
    revision = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True
    ).strip()
    source = subprocess.check_output(['git', 'show', revision + ':' + SOURCE])
    test = Path('tests/unit/orm/test_nonstored_relation_delete_contract.py')
    with TemporaryDirectory(prefix='virtual-delete-source-') as directory:
        snapshot = Path(directory) / 'fields_relational.py'
        snapshot.write_bytes(source)
        finder = RelationalSnapshot(snapshot)
        sys.meta_path.insert(0, finder)
        try:
            django.setup()
            spec = importlib.util.spec_from_file_location(
                'virtual_delete_fixture', test
            )
            fixture = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fixture)
            if Path(sys.modules[MODULE].__file__) != snapshot:
                raise RuntimeError('Published relational source not imported')
            target = fixture.VirtualDeleteTarget
            origin = fixture.VirtualDeleteSource
            field = origin._meta.get_field('target')
            assert {f.name for f in target._meta.concrete_fields} == {
                'id', 'label'
            }
            assert {f.name for f in origin._meta.concrete_fields} == {'id'}
            target_table = connection.ops.quote_name(target._meta.db_table)
            origin_table = connection.ops.quote_name(origin._meta.db_table)
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database(), version()')
                database, version = cursor.fetchone()
                assert database == 'postgres' and version.startswith(
                    'PostgreSQL 16.'
                )
                automation = apps.get_model(
                    'base_automation', 'BaseAutomation'
                )
                assert automation._meta.db_table == 'base_automation'
                columns = []
                for concrete in automation._meta.concrete_fields:
                    column_type = concrete.db_type(connection)
                    assert concrete.column and column_type
                    column = connection.ops.quote_name(concrete.column)
                    columns.append(f'{column} {column_type}')
                automation_table = connection.ops.quote_name(
                    automation._meta.db_table
                )
                cursor.execute(
                    f'CREATE TEMP TABLE {automation_table} '
                    '(' + ', '.join(columns) + ')'
                )
                cursor.execute(
                    f'CREATE TEMP TABLE {target_table} '
                    '(id bigint PRIMARY KEY, label varchar(32) NOT NULL)'
                )
                cursor.execute(
                    f'CREATE TEMP TABLE {origin_table} (id bigint PRIMARY KEY)'
                )
                cursor.execute(
                    f'INSERT INTO {target_table} VALUES (31, %s), (32, %s)',
                    ['positive', 'negative'],
                )
                cursor.execute(f'INSERT INTO {origin_table} VALUES (41)')
            count, _ = target.objects.get(pk=31).delete()
            assert count == 1
            assert not target.objects.filter(pk=31).exists()
            assert origin.objects.filter(pk=41).exists()
            negative_error = None
            try:
                with transaction.atomic():
                    with patch.object(
                        field.remote_field, 'on_delete', models.SET_NULL
                    ):
                        target.objects.get(pk=32).delete()
            except (FieldError, TypeError) as error:
                negative_error = type(error).__name__
            assert negative_error is not None, 'Policy annulment did not fail'
            assert target.objects.filter(pk=32).exists()
            assert origin.objects.filter(pk=41).exists()
            result = {
                'source_revision': revision,
                'source_sha256': hashlib.sha256(source).hexdigest(),
                'test_sha256': hashlib.sha256(test.read_bytes()).hexdigest(),
                'postgresql_version': version,
                'class_body_field_declaration': True,
                'published_factory_imported': True,
                'delete_target_succeeded': True,
                'source_row_preserved': True,
                'annulled_policy_error': negative_error,
                'negative_target_preserved': True,
                'temporary_tables_only': True,
                'application_signals': (
                    'Enabled; empty temporary automation-rule fixture supplied'
                ),
                'acceptance': (
                    'Bounded delete behavior; not full TASK acceptance'
                ),
            }
            (JOB / 'outputs/nonstored-delete-postgresql.json').write_text(
                json.dumps(result, indent=2) + '\n'
            )
            print(json.dumps(result))
        finally:
            connection.close()
            sys.meta_path.remove(finder)


if __name__ == '__main__':
    main()
