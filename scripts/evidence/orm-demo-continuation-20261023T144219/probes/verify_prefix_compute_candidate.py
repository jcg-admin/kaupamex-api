"""Check the exact staged analytic prefix callback without opening SQL.

Account queries are mocked by the consumer tests. This does not qualify
company-domain equivalence, persistence or the complete dependency graph.
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

SOURCE = 'addons/account/models/account_analytic_distribution_model.py'
MODULE = 'addons.account.models.account_analytic_distribution_model'
TEST = 'tests/unit/account/test_analytic_prefix_compute_contract.py'


class PrefixSnapshot(importlib.abc.MetaPathFinder):
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
    parser.add_argument('--annul-compute', action='store_true')
    args = parser.parse_args()
    if MODULE in sys.modules or settings.configured:
        raise RuntimeError('Prefix candidate requires a fresh process')
    head, index = git('rev-parse', 'HEAD'), git('write-tree')
    source = subprocess.check_output(['git', 'show', ':' + SOURCE])
    if args.annul_compute:
        source = source.replace(
            b'compute=_compute_prefix_placeholder,',
            b'default=_compute_prefix_placeholder,',
        )
    test_hash = hashlib.sha256(Path(TEST).read_bytes()).hexdigest()
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        for key, value in {
            'NAME': 'prefix_compute_no_connection',
            'USER': 'prefix_compute_no_connection',
            'PASSWORD': secrets.token_urlsafe(30),
            'HOST': '127.0.0.1', 'PORT': '1',
            'SSL_MODE': 'disable', 'SOCKET': '',
        }.items():
            os.environ[prefix + key] = value
    with TemporaryDirectory(prefix='prefix-compute-candidate-') as directory:
        snapshot = Path(directory) / 'account_analytic_distribution_model.py'
        snapshot.write_bytes(source)
        finder = PrefixSnapshot(snapshot)
        sys.meta_path.insert(0, finder)
        try:
            with patch(
                'django.db.backends.base.base.BaseDatabaseWrapper.'
                'ensure_connection',
                side_effect=AssertionError('SQL prohibited in prefix tests'),
            ):
                django.setup()
                code = pytest.main([
                    '--noconftest', '-c', 'pyproject.toml', '-o', 'addopts=',
                    '--import-mode=importlib', '-q', '--tb=line', TEST,
                    f'--junitxml={args.result.with_suffix(".junit.xml")}',
                ])
                if Path(sys.modules[MODULE].__file__) != snapshot:
                    raise RuntimeError('Staged prefix source not imported')
        finally:
            sys.meta_path.remove(finder)
    stable = head == git('rev-parse', 'HEAD') and index == git('write-tree')
    stable = stable and test_hash == hashlib.sha256(
        Path(TEST).read_bytes()
    ).hexdigest()
    result = {
        'head': head, 'index_tree': index,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'test_sha256': test_hash, 'annulled_compute': args.annul_compute,
        'pytest_exit_code': int(code), 'provenance_unchanged': stable,
        'scope': 'Staged analytic source, actual Django model and descriptor; '
                 'mocked account queries; SQL prohibited; not acceptance',
    }
    args.result.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return int(code) if code else (0 if stable else 2)


if __name__ == '__main__':
    raise SystemExit(main())
