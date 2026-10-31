"""Real SQL/savepoint dependency with optional reporter deliberately absent."""
from contextlib import nullcontext
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import django

django.setup()

from django.conf import settings
from django.db import connection, transaction
from modules.loading import load_demo
from orm.environments import Environment

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
root = Path(__file__).resolve().parents[4]


class OptionalReporterEnvironment:
    cr = connection
    context = {}

    def __getitem__(self, name):
        raise KeyError(name)

    def __call__(self, **overrides):
        return Environment(cr='default', uid=42, **overrides)

    def ref(self, name, raise_if_not_found=True):
        return None


with TemporaryDirectory(prefix='demo_savepoint_', dir=root/'addons') as directory:
    path = Path(directory)
    (path/'insert.sql').write_text('INSERT INTO contract_demo_savepoint_events VALUES (1)')
    (path/'failure.sql').write_text("SELECT CAST('expected-demo-error' AS integer)")
    package = SimpleNamespace(name=path.name, id=0, manifest={'demo':['insert.sql']})
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE contract_demo_savepoint_events (value integer)')
    try:
        with transaction.atomic():
            assert load_demo(OptionalReporterEnvironment(), package, {}, 'init') is True
            with connection.cursor() as cursor:
                cursor.execute('SELECT count(*) FROM contract_demo_savepoint_events')
                assert cursor.fetchone() == (1,)
                cursor.execute('DELETE FROM contract_demo_savepoint_events')
            package.manifest['demo'] = ['insert.sql','failure.sql']
            mutation = mock.patch('modules.loading.transaction.atomic', return_value=nullcontext()) if '--annul-savepoint' in sys.argv else nullcontext()
            with mutation:
                assert load_demo(OptionalReporterEnvironment(), package, {}, 'init') is False
            with connection.cursor() as cursor:
                cursor.execute('SELECT count(*) FROM contract_demo_savepoint_events')
                assert cursor.fetchone() == (0,)
    finally:
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE contract_demo_savepoint_events')
print(json.dumps({'real_files_converter_and_pg':True,'failed_stage_rolled_back':True,
                  'outer_transaction_usable':True,'limits':'Optional failure model absent in fixture; actual reporter verified separately on full schema'}))
