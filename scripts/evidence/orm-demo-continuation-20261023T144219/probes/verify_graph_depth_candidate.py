"""Verify the staged graph depth change with isolated PostgreSQL settings.

No database is opened. Existing catalogue fixtures mock their model reads;
this qualifies graph behavior, not application bootstrap or loader acceptance.
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

from django.conf import settings
import pytest

JOB = Path(__file__).resolve().parents[1]
SOURCE = 'src/modules/module_graph.py'
TESTS = (
    'tests/unit/modules/test_module_graph.py',
    'tests/unit/modules/test_module_graph_depth_limits.py',
)


class GraphSnapshot(importlib.abc.MetaPathFinder):
    def __init__(self, source):
        self.source = source

    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'modules.module_graph':
            return importlib.util.spec_from_file_location(
                fullname, self.source
            )
        return None


def git(*args):
    return subprocess.check_output(['git', *args]).decode().strip()


def depth_node(source):
    cls = next(n for n in ast.parse(source).body
               if isinstance(n, ast.ClassDef) and n.name == 'ModuleGraph')
    return next(n for n in cls.body
                if isinstance(n, ast.FunctionDef) and n.name == '_depth')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--annul-depth', action='store_true')
    args = parser.parse_args()
    if settings.configured or 'modules.module_graph' in sys.modules:
        raise RuntimeError('Graph candidate needs a fresh test process')
    head, index = git('rev-parse', 'HEAD'), git('write-tree')
    source = subprocess.check_output(['git', 'show', ':' + SOURCE])
    if args.annul_depth:
        old = (JOB / 'outputs/depth-limit-preserved-working-graph.py.txt')
        previous = old.read_text().splitlines(keepends=True)
        old_node = depth_node(''.join(previous))
        current = source.decode().splitlines(keepends=True)
        node = depth_node(''.join(current))
        source = ''.join(
            current[:node.lineno - 1]
            + previous[old_node.lineno - 1:old_node.end_lineno]
            + current[node.end_lineno:]
        ).encode()
    test_hashes = {
        name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
        for name in TESTS
    }
    os.environ.pop('DJANGO_SETTINGS_MODULE', None)
    settings.configure(
        SECRET_KEY=secrets.token_urlsafe(50), INSTALLED_APPS=[], USE_TZ=True,
        DATABASES={'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'graph_depth_no_connection',
            'HOST': '127.0.0.1', 'PORT': '1',
        }},
    )
    with TemporaryDirectory(prefix='graph-depth-candidate-') as temporary:
        snapshot = Path(temporary) / 'module_graph.py'
        snapshot.write_bytes(source)
        finder = GraphSnapshot(snapshot)
        sys.meta_path.insert(0, finder)
        try:
            with patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.'
                'ensure_connection',
                side_effect=AssertionError('SQL prohibited in depth tests'),
            ):
                code = pytest.main([
                    '--noconftest', '-c', 'pyproject.toml', '-o', 'addopts=',
                    '--import-mode=importlib', '-q', '--tb=line', *TESTS,
                    f'--junitxml={args.result.with_suffix(".junit.xml")}',
                ])
                loaded = sys.modules['modules.module_graph'].__file__
                if Path(loaded) != snapshot:
                    raise RuntimeError('Graph candidate source not imported')
        finally:
            sys.meta_path.remove(finder)
    stable = head == git('rev-parse', 'HEAD') and index == git('write-tree')
    stable = stable and all(
        hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
        for name, expected in test_hashes.items()
    )
    result = {
        'head': head, 'index_tree': index,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'test_sha256': test_hashes, 'annulled_depth': args.annul_depth,
        'pytest_exit_code': int(code), 'provenance_unchanged': stable,
        'scope': 'Exact staged graph or declared in-memory annulment; minimal '
                 'Django PostgreSQL settings; SQL prohibited; no acceptance',
    }
    args.result.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(code) if code else (0 if stable else 2)


if __name__ == '__main__':
    raise SystemExit(main())
