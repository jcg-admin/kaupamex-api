"""Verify staged descriptor/environment sources with SQL prohibited.

UID-only mode keeps the published descriptor. Annulments change only the
declared descriptor bindings or UID conditional in an in-memory snapshot.
"""

import argparse
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
from django.conf import settings
import pytest

SOURCES = {
    'orm.environments': 'src/orm/environments.py',
    'orm.fields': 'src/orm/fields.py',
}
UID_TEST = 'tests/unit/orm/test_uid_cache_key_contract.py'
RECORD_TEST = 'tests/unit/orm/test_record_environment_field_contract.py'
COMPANY_TEST = 'tests/unit/orm/test_environments_cache.py'
COMPANY_CASES = (
    (COMPANY_TEST + '::'
     'test_allowed_company_cache_key_tracks_the_validated_channel'),
    (COMPANY_TEST + '::'
     'test_allowed_company_cache_key_normalizes_explicit_lists'),
)
REGRESSIONS = (
    'tests/unit/orm/test_field_cache.py::TestTheMappingIsStable',
    'tests/unit/orm/test_field_cache.py::TestTheContextSplitsTheCache',
    'tests/unit/orm/test_field_cache.py::TestInvalidationRemovesWhatItSays',
    'tests/unit/orm/test_environments_channels.py',
    'tests/unit/orm/test_nonstored_compute_dispatch.py',
    'tests/unit/account/test_analytic_prefix_compute_contract.py',
)


class RecordEnvironmentSnapshot(importlib.abc.MetaPathFinder):
    def __init__(self, paths):
        self.paths = paths

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.paths:
            return importlib.util.spec_from_file_location(
                fullname, self.paths[fullname]
            )
        return None


def git(*args):
    return subprocess.check_output(['git', *args]).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--uid-only', action='store_true')
    parser.add_argument('--annul-descriptor', action='store_true')
    parser.add_argument('--annul-uid', action='store_true')
    parser.add_argument('--regression', action='store_true')
    parser.add_argument('--annul-canonical-scope', action='store_true')
    parser.add_argument('--annul-record-sudo', action='store_true')
    parser.add_argument('--keyword-only', action='store_true')
    parser.add_argument('--batch-only', action='store_true')
    parser.add_argument('--annul-native-batch', action='store_true')
    args = parser.parse_args()
    if args.uid_only and args.annul_descriptor:
        parser.error('UID-only mode has no staged descriptor to annul')
    if settings.configured or any(name in sys.modules for name in SOURCES):
        raise RuntimeError('Candidate verification needs a fresh process')
    head, index = git('rev-parse', 'HEAD'), git('write-tree')
    snapshots = {}
    origins = {}
    for module, path in SOURCES.items():
        origin = 'HEAD:' if args.uid_only and module == 'orm.fields' else ':'
        origins[module] = origin + path
        snapshots[module] = subprocess.check_output(
            ['git', 'show', origin + path]
        )
    if args.annul_native_batch:
        source = snapshots['orm.fields']
        start = source.index(b'def _invoke_compute_method(')
        end = source.index(b'\ndef recompute(', start)
        body = source[start:end]
        original = b'for record in as_record_list(records):'
        replacement = (
            b'for record in (list(records) if '
            b'getattr(records, "_ids", None) is not None '
            b'else as_record_list(records)):'
        )
        if body.count(original) != 1:
            raise RuntimeError('Native dispatch not uniquely identified')
        snapshots['orm.fields'] = (
            source[:start] + body.replace(original, replacement) + source[end:]
        )
    if args.annul_uid:
        source = snapshots['orm.environments']
        expression = b'self.uid if field.compute_sudo else (self.uid, self.su)'
        if source.count(expression) != 1:
            raise RuntimeError('UID conditional not uniquely identified')
        snapshots['orm.environments'] = source.replace(expression, b'self.uid')
    if args.annul_descriptor:
        source = snapshots['orm.fields']
        for name in ('__get__', '__set__'):
            binding = (
                f'FieldDescriptor.{name} = '
                f'_in_record_environment(FieldDescriptor.{name})\n'
            ).encode()
            if source.count(binding) != 1:
                raise RuntimeError(
                    'Descriptor binding not uniquely identified'
                )
            source = source.replace(binding, b'')
        snapshots['orm.fields'] = source
    if args.annul_canonical_scope:
        source = snapshots['orm.fields']
        if source.count(b'with attached():') != 1:
            raise RuntimeError('Canonical scope not uniquely identified')
        snapshots['orm.fields'] = source.replace(
            b'with attached():', b'with attached:'
        )
    if args.annul_record_sudo:
        source = snapshots['orm.fields']
        branch = (
            b"    if self.compute_sudo and getattr(records, '_ids', None) "
            b"is not None:\n        records = records.sudo()\n"
        )
        if source.count(branch) != 1:
            raise RuntimeError('Record sudo branch not uniquely identified')
        snapshots['orm.fields'] = source.replace(branch, b'')
    tests = [UID_TEST, *COMPANY_CASES]
    if not args.uid_only:
        tests.insert(0, RECORD_TEST)
    if args.regression:
        tests.extend(REGRESSIONS)
    if args.annul_canonical_scope:
        tests = [
            RECORD_TEST + '::test_shared_attached_environment_scopes_'
            'are_local_to_each_thread'
        ]
    if args.annul_record_sudo:
        tests = [
            RECORD_TEST + '::test_compute_sudo_receives_an_elevated_record_'
            'and_restores_the_caller',
            RECORD_TEST + '::test_compute_sudo_assignment_keeps_the_'
            'elevated_channel',
        ]
    if args.keyword_only:
        tests = [RECORD_TEST + '::'
                 'test_explicit_descriptor_self_keyword_remains_compatible']
    if args.batch_only:
        tests = ['tests/unit/orm/test_native_compute_batch_dispatch.py']
    test_hashes = {
        path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in {test.split('::')[0] for test in tests}
    }
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        for key, value in {
            'NAME': 'record_env_no_connection',
            'USER': 'record_env_no_connection',
            'PASSWORD': secrets.token_urlsafe(30),
            'HOST': '127.0.0.1', 'PORT': '1',
            'SSL_MODE': 'disable', 'SOCKET': '',
        }.items():
            os.environ[prefix + key] = value
    with TemporaryDirectory(prefix='record-env-candidate-') as directory:
        paths = {}
        for module, source in snapshots.items():
            paths[module] = Path(directory) / (module.split('.')[-1] + '.py')
            paths[module].write_bytes(source)
        finder = RecordEnvironmentSnapshot(paths)
        sys.meta_path.insert(0, finder)
        try:
            with patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.'
                'ensure_connection',
                side_effect=AssertionError('SQL prohibited in record tests'),
            ):
                django.setup()
                code = pytest.main([
                    '--noconftest', '-c', 'pyproject.toml', '-o', 'addopts=',
                    '--import-mode=importlib', '-q', '--tb=line', *tests,
                    f'--junitxml={args.result.with_suffix(".junit.xml")}',
                ])
                for module, path in paths.items():
                    if Path(sys.modules[module].__file__) != path:
                        raise RuntimeError('Candidate not imported: ' + module)
        finally:
            sys.meta_path.remove(finder)
    stable = head == git('rev-parse', 'HEAD') and index == git('write-tree')
    stable = stable and all(
        hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
        for path, expected in test_hashes.items()
    )
    result = {
        'head': head, 'index_tree': index, 'origins': origins,
        'source_sha256': {
            module: hashlib.sha256(source).hexdigest()
            for module, source in snapshots.items()
        },
        'test_sha256': test_hashes, 'uid_only': args.uid_only,
        'annul_descriptor': args.annul_descriptor,
        'annul_uid': args.annul_uid, 'regression': args.regression,
        'annul_canonical_scope': args.annul_canonical_scope,
        'annul_record_sudo': args.annul_record_sudo,
        'keyword_only': args.keyword_only,
        'batch_only': args.batch_only,
        'annul_native_batch': args.annul_native_batch,
        'pytest_exit': int(code), 'provenance_unchanged': stable,
        'scope': 'Exact declared source snapshots and hashed Consumer tests; '
                 'SQL prohibited; no whole-head CI/integration/acceptance',
    }
    args.result.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(code) if code else (0 if stable else 2)


if __name__ == '__main__':
    raise SystemExit(main())
