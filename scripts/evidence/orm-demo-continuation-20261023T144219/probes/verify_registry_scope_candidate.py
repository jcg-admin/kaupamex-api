"""Verify the exact staged Registry while preserving unrelated local edits."""

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
import pytest


class RegistrySnapshot(importlib.abc.MetaPathFinder):
    def __init__(self, source):
        self.source = source

    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'orm.registry':
            return importlib.util.spec_from_file_location(
                fullname, self.source
            )
        return None


def git(*args):
    return subprocess.check_output(['git', *args]).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    head, index = git('rev-parse', 'HEAD'), git('write-tree')
    source = subprocess.check_output([
        'git', 'show', ':src/orm/registry.py',
    ])
    if 'orm.registry' in sys.modules:
        raise RuntimeError('Registry was imported before candidate isolation')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        values = {
            'NAME': 'orm_flag_no_connection',
            'USER': 'orm_flag_no_connection',
            'PASSWORD': secrets.token_urlsafe(32),
            'HOST': '127.0.0.1', 'PORT': '1',
            'SSL_MODE': 'disable', 'SOCKET': '',
        }
        for key, value in values.items():
            os.environ[prefix + key] = value
    with TemporaryDirectory(prefix='registry-scope-candidate-') as temporary:
        snapshot = Path(temporary) / 'registry.py'
        snapshot.write_bytes(source)
        finder = RegistrySnapshot(snapshot)
        sys.meta_path.insert(0, finder)
        try:
            with patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.'
                'ensure_connection',
                side_effect=AssertionError('SQL prohibited in flag tests'),
            ):
                django.setup()
                loaded_from = sys.modules['orm.registry'].__file__
                if Path(loaded_from) != snapshot:
                    raise RuntimeError('Candidate source was not imported')
                code = pytest.main([
                    '--noconftest', '-c', '/dev/null', '-o', 'addopts=',
                    '--import-mode=importlib', '-q',
                    'tests/unit/orm/test_registry_invalidation_scope.py',
                    'tests/unit/orm/test_registry_class.py',
                    f'--junitxml={args.result.with_suffix(".junit.xml")}',
                ])
        finally:
            sys.meta_path.remove(finder)
    stable = head == git('rev-parse', 'HEAD') and index == git('write-tree')
    report = {
        'head': head, 'index_tree': index,
        'staged_registry_sha256': hashlib.sha256(source).hexdigest(),
        'pytest_exit_code': code, 'git_provenance_unchanged': stable,
        'scope': 'Exact staged Registry; other Consumer sources remain '
                 'working-tree dependencies; SQL prohibited; no acceptance',
    }
    args.result.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return code if code else (0 if stable else 2)


if __name__ == '__main__':
    raise SystemExit(main())
