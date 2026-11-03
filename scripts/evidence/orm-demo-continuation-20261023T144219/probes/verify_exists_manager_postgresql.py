"""Qualify physical existence against an explicitly owned PostgreSQL server.

Only a temporary table is created. Container lifecycle and credentials are
supplied by the terminal operation, not a Consumer coordination mechanism.
"""

import ast
import hashlib
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
from django.db import connection
from django.test.utils import CaptureQueriesContext

from verify_exists_manager_candidate import ExistsSnapshot, MODULE, SOURCE

JOB = Path(__file__).resolve().parents[1]


def main():
    password = os.environ['ORM_EXISTS_PASSWORD']
    port = os.environ['ORM_EXISTS_PORT']
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        for key, value in {
            'NAME': 'postgres', 'USER': 'postgres', 'PASSWORD': password,
            'HOST': '127.0.0.1', 'PORT': port,
            'SSL_MODE': 'disable', 'SOCKET': '',
        }.items():
            os.environ[prefix + key] = value
    revision = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True
    ).strip()
    source = subprocess.check_output(['git', 'show', revision + ':' + SOURCE])
    with TemporaryDirectory(prefix='exists-pg-source-') as directory:
        snapshot = Path(directory) / 'models.py'
        snapshot.write_bytes(source)
        finder = ExistsSnapshot(snapshot)
        sys.meta_path.insert(0, finder)
        try:
            django.setup()
            if Path(sys.modules[MODULE].__file__) != snapshot:
                raise RuntimeError('Published model source not imported')
            test_path = Path('tests/unit/orm/test_exists_manager_contract.py')
            spec = importlib.util.spec_from_file_location(
                'exists_postgresql_fixture', test_path
            )
            fixture = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fixture)
            model = fixture.ExistsManagerProbe
            assert {f.name for f in model._meta.concrete_fields} == {
                'id', 'visible'
            }
            table = connection.ops.quote_name(model._meta.db_table)
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database(), version()')
                database, version = cursor.fetchone()
                assert database == 'postgres' and version.startswith(
                    'PostgreSQL 16.'
                )
                cursor.execute(
                    f'CREATE TEMP TABLE {table} '
                    '(id bigint PRIMARY KEY, visible boolean NOT NULL)'
                )
                cursor.execute(
                    f'INSERT INTO {table} (id, visible) VALUES '
                    '(11, false), (22, true)'
                )
            assert tuple(model.objects.values_list('pk', flat=True)) == (22,)
            fresh = fixture.NewId()
            records = fixture.records((11, fresh, 88, 22, 11))
            with CaptureQueriesContext(connection) as queries:
                actual = records.exists()
            assert actual._ids == (11, fresh, 22, 11)
            assert actual.env is records.env
            assert len(queries) == 1
            for ids in ((), (fixture.NewId(),)):
                original = fixture.records(ids)
                with CaptureQueriesContext(connection) as queries:
                    assert original.exists() is original
                assert not queries
            assert fixture.records((88,)).exists()._ids == ()
            cls = next(n for n in ast.parse(source).body
                       if isinstance(n, ast.ClassDef)
                       and n.name == 'BaseModel')
            method = next(n for n in cls.body
                          if isinstance(n, ast.FunctionDef)
                          and n.name == 'exists')
            for node in ast.walk(method):
                if isinstance(node, ast.Attribute):
                    if node.attr == '_base_manager':
                        node.attr = '_default_manager'
            namespace = dict(vars(sys.modules[MODULE]))
            exec(compile(ast.Module(body=[method], type_ignores=[]),
                         '<annulled exists manager>', 'exec'), namespace)
            with patch.object(
                fixture.BaseModel, 'exists', namespace['exists']
            ):
                negative = records.exists()
            assert negative._ids == (fresh, 22)
            result = {
                'revision': revision,
                'source_sha256': hashlib.sha256(source).hexdigest(),
                'postgresql_version': version,
                'actual_hidden_row_retained': True,
                'order_duplicates_new_ids_preserved': True,
                'missing_rows_removed': True,
                'empty_and_new_only_no_query': True,
                'annulled_manager_loses_hidden_row': True,
                'temporary_table_only': True,
                'acceptance': (
                    'not_verified: full routing/security/ORM excluded'
                ),
            }
            (JOB / 'outputs/exists-manager-postgresql.json').write_text(
                json.dumps(result, indent=2) + '\n'
            )
            print(json.dumps(result))
        finally:
            connection.close()
            sys.meta_path.remove(finder)


if __name__ == '__main__':
    main()
