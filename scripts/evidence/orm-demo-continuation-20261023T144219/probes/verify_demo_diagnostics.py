"""Run demo diagnostic contracts without connecting to any database.

This bounded verifier initializes the actual Consumer and runs its maintained
tests. PostgreSQL configuration is deliberately unreachable; SQL is refused.
It does not demonstrate installation, migration or physical persistence.
"""

import os
from pathlib import Path
import secrets
import sys
from unittest.mock import patch

import django
import pytest


def main():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(50)
    for prefix in ('DB_', 'DB_QA_'):
        values = {
            'NAME': 'orm_diagnostic_no_connection',
            'USER': 'orm_diagnostic_no_connection',
            'PASSWORD': secrets.token_urlsafe(32),
            'HOST': '127.0.0.1',
            'PORT': '1',
            'SSL_MODE': 'disable',
            'SOCKET': '',
        }
        for key, value in values.items():
            os.environ[prefix + key] = value
    output = Path(sys.argv[1])
    with patch(
        'django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',
        side_effect=AssertionError('SQL prohibited in diagnostic contracts'),
    ):
        django.setup()
        return pytest.main([
            '--noconftest', '-c', '/dev/null', '-o', 'addopts=',
            '--import-mode=importlib', '-q',
            'tests/unit/modules/test_loading_demo.py',
            'tests/unit/modules/test_loading.py',
            f'--junitxml={output}',
            *sys.argv[2:],
        ])


if __name__ == '__main__':
    sys.exit(main())
