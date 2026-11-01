"""Qualify native recompute absence retries against owned PostgreSQL.

The terminal provisions a disposable server. This probe creates only a TEMP
fixture table and loads declared Git source snapshots, without migrations.
"""

import argparse
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
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from verify_record_environment_candidate import RecordEnvironmentSnapshot

JOB = Path(__file__).resolve().parents[1]
SOURCES = {
    'orm.fields': 'src/orm/fields.py',
    'orm.environments': 'src/orm/environments.py',
    'orm.models': 'src/orm/models.py',
}
FIXTURE = 'tests/unit/orm/test_native_pending_recompute.py'
OLD_REVISION = '92a84833f01d5d4c54aaf5df3a9ba74cdd0c4773'


def git_source(revision, path):
    return subprocess.check_output(['git', 'show', revision + ':' + path])


def verify_stored_m2m(revision, sources, directory):
    fixture_name = 'tests/unit/orm/test_native_stored_compute_contract.py'
    fixture_source = git_source(revision, fixture_name)
    fixture_path = Path(directory) / 'stored_fixture.py'
    fixture_path.write_bytes(fixture_source)
    spec = importlib.util.spec_from_file_location(
        'native_stored_pg_fixture', fixture_path
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    target = fixture.NativeStoredProbe
    model = fixture.NativeStoredRelationProbe
    field = model._meta.get_field('members')
    through = field.remote_field.through
    names = {item._meta.db_table for item in (target, model, through)}
    assert all(name.startswith('contenttypes_native') for name in names)
    with connection.cursor() as cursor:
        cursor.execute('SELECT version()')
        version = cursor.fetchone()[0]
        assert version.startswith('PostgreSQL 16.')
    with connection.schema_editor(collect_sql=True) as editor:
        editor.create_model(target)
        editor.create_model(model)
    executed_schema = []
    with connection.cursor() as cursor:
        for statement in editor.collected_sql:
            if statement.startswith('CREATE TABLE '):
                statement = statement.replace(
                    'CREATE TABLE ', 'CREATE TEMP TABLE ', 1
                )
            elif not statement.startswith((
                'ALTER TABLE ', 'CREATE INDEX ', 'CREATE UNIQUE INDEX '
            )):
                raise RuntimeError('Unexpected fixture SQL: ' + statement)
            cursor.execute(statement)
            executed_schema.append(statement)
        target_table = connection.ops.quote_name(target._meta.db_table)
        parent_table = connection.ops.quote_name(model._meta.db_table)
        through_table = connection.ops.quote_name(through._meta.db_table)
        cursor.execute(
            f'INSERT INTO {target_table} (id, computed) '
            'VALUES (131, %s), (132, %s)', ['target131', 'target132']
        )
        cursor.execute(f'INSERT INTO {parent_table} (id) VALUES (31), (32)')
    expected = {31: [131], 32: [132]}
    fixture.registry.clear_field_depends()
    with fixture.transaction_scope():
        records = model._from_ids(fixture.env(), (31, 32), (31, 32))
        with CaptureQueriesContext(connection) as queries:
            field.compute_value(records)
        actual = {
            id_: [item.pk for item in values]
            for id_, values in field._get_cache(fixture.env()).items()
        }
        assert actual == expected, actual
        assert fixture.env().transaction.field_dirty[field] == {31, 32}
        positive_sql = [query['sql'] for query in queries]
    left = connection.ops.quote_name(
        through._meta.get_field(field.m2m_field_name()).column
    )
    right = connection.ops.quote_name(
        through._meta.get_field(field.m2m_reverse_field_name()).column
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT {left}, {right} FROM {through_table} '
            f'ORDER BY {left}, {right}'
        )
        positive_links = cursor.fetchall()
        assert positive_links == [(31, 131), (32, 132)]
        cursor.execute(f'DELETE FROM {through_table}')
    old_revision = '4166b38d4b06fb7af77acfa5d458c84cffdc2fda'
    old_source = git_source(old_revision, SOURCES['orm.fields'])
    old_helper = next(
        node for node in ast.parse(old_source).body
        if isinstance(node, ast.FunctionDef)
        and node.name == '_cache_computed_values'
    )
    isolated = dict(sys.modules['orm.fields'].__dict__)
    exec(compile(
        ast.Module(body=[old_helper], type_ignores=[]),
        old_revision + ':native_stored_readback', 'exec'
    ), isolated)
    with patch.object(
        sys.modules['orm.fields'], '_cache_computed_values',
        isolated['_cache_computed_values']
    ), fixture.transaction_scope():
        records = model._from_ids(fixture.env(), (31, 32), (31, 32))
        field.compute_value(records)
        negative_cache = {
            id_: [item.pk for item in values]
            for id_, values in field._get_cache(fixture.env()).items()
        }
        assert negative_cache != expected, 'Read-back annulment did not fail'
        negative_dirty = sorted(
            fixture.env().transaction.field_dirty.get(field, set())
        )
    fixture.registry.clear_field_depends()
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT {left}, {right} FROM {through_table} '
            f'ORDER BY {left}, {right}'
        )
        negative_links = cursor.fetchall()
        assert negative_links == positive_links
        cursor.execute(
            'SELECT count(*) FROM pg_tables WHERE schemaname = %s', ['public']
        )
        assert cursor.fetchone()[0] == 0
    return {
        'source_revision': revision,
        'source_sha256': {
            module: hashlib.sha256(source).hexdigest()
            for module, source in sources.items()
        },
        'fixture_sha256': hashlib.sha256(fixture_source).hexdigest(),
        'postgresql_version': version,
        'actual_m2m_set_and_all': True,
        'temporary_schema': executed_schema,
        'positive_cache': actual, 'positive_links': positive_links,
        'positive_dirty': [31, 32], 'positive_sql': positive_sql,
        'negative_revision': old_revision,
        'negative_source_sha256': hashlib.sha256(old_source).hexdigest(),
        'negative_cache': negative_cache, 'negative_dirty': negative_dirty,
        'negative_links_preserved': negative_links,
        'temporary_tables_only': True, 'public_tables': 0,
        'acceptance': (
            'Actual M2M manager SQL and read-back qualified for fixture; '
            'not complete flush, permissions or ORM acceptance'
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m2m-only', action='store_true')
    args = parser.parse_args()
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        for key, value in {
            'NAME': 'postgres', 'USER': 'postgres',
            'PASSWORD': os.environ['ORM_NATIVE_PG_PASSWORD'],
            'HOST': '127.0.0.1', 'PORT': os.environ['ORM_NATIVE_PG_PORT'],
            'SSL_MODE': 'disable', 'SOCKET': '',
        }.items():
            os.environ[prefix + key] = value
    revision = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True
    ).strip()
    sources = {
        module: git_source(revision, path)
        for module, path in SOURCES.items()
    }
    fixture_source = git_source(revision, FIXTURE)
    with TemporaryDirectory(prefix='native-pending-pg-source-') as directory:
        paths = {}
        for module, source in sources.items():
            path = Path(directory) / (module.split('.')[-1] + '.py')
            path.write_bytes(source)
            paths[module] = path
        finder = RecordEnvironmentSnapshot(paths)
        sys.meta_path.insert(0, finder)
        try:
            django.setup()
            if args.m2m_only:
                for module, path in paths.items():
                    assert Path(sys.modules[module].__file__) == path, module
                with transaction.atomic():
                    result = verify_stored_m2m(revision, sources, directory)
                    transaction.set_rollback(True)
                result['outer_transaction_rolled_back'] = True
                result['commit_flush_qualification'] = (
                    'BLOCKED by missing bootstrap fixture; preserved '
                    'non-rollback attempt in bootstrap-boundary receipt'
                )
                (JOB / 'outputs/native-stored-postgresql.json').write_text(
                    json.dumps(result, indent=2) + '\n'
                )
                print(json.dumps(result))
                return
            fixture_path = Path(directory) / 'pending_fixture.py'
            fixture_path.write_bytes(fixture_source)
            spec = importlib.util.spec_from_file_location(
                'native_pending_pg_fixture', fixture_path
            )
            fixture = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fixture)
            for module, path in paths.items():
                assert Path(sys.modules[module].__file__) == path, module
            model = fixture.NativePendingProbe
            field = model._meta.get_field('value')
            assert {f.name for f in model._meta.concrete_fields} == {
                'id', 'value'
            }
            table = connection.ops.quote_name(model._meta.db_table)
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database(), version()')
                database, version = cursor.fetchone()
                assert database == 'postgres'
                assert version.startswith('PostgreSQL 16.')
                cursor.execute(
                    f'CREATE TEMP TABLE {table} '
                    '(id bigint PRIMARY KEY, value varchar(32))'
                )
                cursor.execute(
                    f'INSERT INTO {table} VALUES (31, %s), (33, %s)',
                    ['row31', 'row33'],
                )
            calls = []

            def compute(batch):
                calls.append(batch._ids)
                for record in batch:
                    stored = model._base_manager.get(pk=record._ids[0])
                    record.value = 'computed:' + stored.__dict__['value']

            with patch.object(field, 'compute', compute):
                fixture.registry.clear_field_depends()
                with fixture.transaction_scope():
                    records = model._from_ids(
                        fixture.env(), (31, 32, 33), (31, 32, 33)
                    )
                    fixture.env().add_to_compute(field, records._ids)
                    with CaptureQueriesContext(connection) as queries:
                        field.recompute(records)
                    positive_calls = list(calls)
                    positive_sql = [query['sql'] for query in queries]
                    positive_cache = dict(field._get_cache(fixture.env()))
                    assert positive_calls == [(31, 32, 33), (31, 33)]
                    assert positive_cache == {
                        31: 'computed:row31', 33: 'computed:row33'
                    }
                    assert not fixture.env().transaction.tocompute.get(field)
                    assert any(' IN ' in sql for sql in positive_sql)
                calls.clear()
                with fixture.transaction_scope():
                    absent = model._from_ids(fixture.env(), (41, 42), (41, 42))
                    fixture.env().add_to_compute(field, absent._ids)
                    with CaptureQueriesContext(connection) as queries:
                        field.recompute(absent)
                    all_missing_sql = [query['sql'] for query in queries]
                    assert calls == [(41, 42)]
                    assert not fixture.env().transaction.tocompute.get(field)
                    assert dict(field._get_cache(fixture.env())) == {}
                old_source = git_source(OLD_REVISION, SOURCES['orm.fields'])
                old_tree = ast.parse(old_source)
                old_helper = next(
                    node for node in old_tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == '_recompute_native_recordset'
                )
                isolated = dict(sys.modules['orm.fields'].__dict__)
                exec(compile(
                    ast.Module(body=[old_helper], type_ignores=[]),
                    OLD_REVISION + ':native_recompute_helper', 'exec'
                ), isolated)
                calls.clear()
                negative_error = None
                with patch.object(
                    sys.modules['orm.fields'], '_recompute_native_recordset',
                    isolated['_recompute_native_recordset']
                ), fixture.transaction_scope():
                    records = model._from_ids(
                        fixture.env(), (31, 32, 33), (31, 32, 33)
                    )
                    fixture.env().add_to_compute(field, records._ids)
                    try:
                        field.recompute(records)
                    except model.DoesNotExist as error:
                        negative_error = type(error).__name__
                    assert negative_error == 'DoesNotExist'
                    assert calls == [(31, 32, 33)]
                    assert set(fixture.env().transaction.tocompute[field]) == {
                        31, 32, 33
                    }
                fixture.registry.clear_field_depends()
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT id, value FROM {table} ORDER BY id')
                rows_after = cursor.fetchall()
                assert rows_after == [(31, 'row31'), (33, 'row33')]
                cursor.execute(
                    'SELECT count(*) FROM pg_tables '
                    'WHERE schemaname = %s', ['public']
                )
                assert cursor.fetchone()[0] == 0
            result = {
                'source_revision': revision,
                'source_sha256': {
                    module: hashlib.sha256(source).hexdigest()
                    for module, source in sources.items()
                },
                'fixture_sha256': hashlib.sha256(fixture_source).hexdigest(),
                'postgresql_version': version,
                'actual_storage_lookup_and_exists': True,
                'positive_calls': positive_calls,
                'positive_cache': positive_cache,
                'positive_sql': positive_sql,
                'all_missing_sql': all_missing_sql,
                'negative_revision': OLD_REVISION,
                'negative_source_sha256': hashlib.sha256(
                    old_source
                ).hexdigest(),
                'negative_error': negative_error,
                'negative_pending_preserved': True,
                'database_rows_unchanged': rows_after,
                'temporary_tables_only': True,
                'public_tables': 0,
                'acceptance': (
                    'Bounded SQL absence/retry qualification; no full TASK, '
                    'flush, prefetch IO or ORM acceptance'
                ),
            }
            (JOB / 'outputs/native-pending-postgresql.json').write_text(
                json.dumps(result, indent=2) + '\n'
            )
            print(json.dumps(result))
        finally:
            connection.close()
            sys.meta_path.remove(finder)


if __name__ == '__main__':
    main()
