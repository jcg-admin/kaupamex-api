"""Check the staged BaseModel existence contract without opening SQL.

Query transport is mocked by the consumer tests. This does not qualify
permissions, persistence, database routing or the entire recordset protocol.
"""

import argparse
import ast
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

SOURCE = 'src/orm/models.py'
MODULE = 'orm.models'
TEST = 'tests/unit/orm/test_exists_manager_contract.py'


class ExistsSnapshot(importlib.abc.MetaPathFinder):
    def __init__(self, source):
        self.source = source

    def find_spec(self, fullname, path=None, target=None):
        if fullname == MODULE:
            return importlib.util.spec_from_file_location(
                fullname, self.source
            )
        return None


def git(*args):
    return subprocess.check_output(['git', *args]).decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--annul-manager', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    if MODULE in sys.modules or settings.configured:
        raise RuntimeError('Exists candidate requires a fresh process')
    head, index = git('rev-parse', 'HEAD'), git('write-tree')
    revision = 'HEAD:' if args.baseline else ':'
    source = subprocess.check_output(['git', 'show', revision + SOURCE])
    if args.annul_manager:
        text = source.decode()
        cls = next(n for n in ast.parse(text).body
                   if isinstance(n, ast.ClassDef) and n.name == 'BaseModel')
        method = next(n for n in cls.body
                      if isinstance(n, ast.FunctionDef) and n.name == 'exists')
        lines = text.splitlines(keepends=True)
        body = ''.join(lines[method.lineno - 1:method.end_lineno])
        if body.count('_base_manager') != 1:
            raise RuntimeError('Expected one existence manager to annul')
        body = body.replace('_base_manager', '_default_manager')
        source = (''.join(lines[:method.lineno - 1]) + body
                  + ''.join(lines[method.end_lineno:])).encode()
    test_hash = hashlib.sha256(Path(TEST).read_bytes()).hexdigest()
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        for key, value in {
            'NAME': 'exists_manager_no_connection',
            'USER': 'exists_manager_no_connection',
            'PASSWORD': secrets.token_urlsafe(30),
            'HOST': '127.0.0.1', 'PORT': '1',
            'SSL_MODE': 'disable', 'SOCKET': '',
        }.items():
            os.environ[prefix + key] = value
    with TemporaryDirectory(prefix='exists-manager-candidate-') as directory:
        snapshot = Path(directory) / 'models.py'
        snapshot.write_bytes(source)
        finder = ExistsSnapshot(snapshot)
        sys.meta_path.insert(0, finder)
        try:
            with patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.'
                'ensure_connection',
                side_effect=AssertionError('SQL prohibited in exists tests'),
            ):
                django.setup()
                code = pytest.main([
                    '--noconftest', '-c', 'pyproject.toml', '-o', 'addopts=',
                    '--import-mode=importlib', '-q', '--tb=line', TEST,
                    f'--junitxml={args.result.with_suffix(".junit.xml")}',
                ])
                if Path(sys.modules[MODULE].__file__) != snapshot:
                    raise RuntimeError('Staged model source not imported')
        finally:
            sys.meta_path.remove(finder)
    stable = head == git('rev-parse', 'HEAD') and index == git('write-tree')
    stable = stable and test_hash == hashlib.sha256(
        Path(TEST).read_bytes()
    ).hexdigest()
    result = {
        'head': head, 'index_tree': index,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'test_sha256': test_hash, 'annulled_manager': args.annul_manager,
        'pytest_exit_code': int(code), 'provenance_unchanged': stable,
        'baseline': args.baseline,
        'scope': 'Declared model source, native manager metadata, mocked '
                 'query transport; SQL prohibited; not acceptance',
    }
    args.result.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(code) if code else (0 if stable else 2)


if __name__ == '__main__':
    raise SystemExit(main())
