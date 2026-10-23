"""Pinned data-stage comparison and real SQL/rollback; not full loader acceptance."""
import __future__
import ast
from copy import deepcopy
import io
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

import django

django.setup()

from django.conf import settings
from django.db import connections, ProgrammingError, transaction

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from counterpart_body import declarations_of
from reference_roots import tree
from modules.loading import load_data

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
source = tree('odoo19c')/'odoo/modules/loading.py'
declaration = next(d for d in declarations_of(source) if d.kind == 'function' and d.name == 'load_data')
namespace = {'_logger': logging.getLogger('pinned_manifest_data')}
exec(compile(ast.Module(body=[declaration.node], type_ignores=[]), str(source), 'exec',
             flags=__future__.annotations.compiler_flag), namespace)
reference = namespace['load_data']
cases = [
    ('data', [], [], []), ('demo', [], [], []),
    ('data', ['legacy.xml'], ['a.xml', 'legacy.xml'], ['demo.xml']),
    ('demo', ['ignored.xml'], ['ignored.xml'], ['demo.xml', 'demo.xml']),
    ('data', [], ['a.sql', 'b.csv'], []),
]
for kind, initial, data, demo in cases:
    package = SimpleNamespace(name='manifest_contract', manifest={
        'init_xml':initial, 'data':data, 'demo':demo})
    observed = []
    refs = {}

    def capture(module, filename, idref, mode, **kwargs):
        assert idref is refs
        observed.append((module, filename, mode, kwargs['noupdate']))

    namespace['convert_file'] = lambda env, *args, **kwargs: capture(*args, **kwargs)
    expected = reference(object(), refs, 'init', kind, deepcopy(package))
    expected_calls = observed[:]
    observed.clear()
    with mock.patch('modules.loading.convert_file', side_effect=capture):
        actual = load_data(refs, 'init', kind, deepcopy(package), using='default')
    assert actual == expected and observed == expected_calls

connection = connections['default']
assert connection.vendor == 'postgresql'
files = {
    'setup.sql': b'CREATE TABLE contract_manifest_events (value integer)',
    'insert.sql': b'INSERT INTO contract_manifest_events VALUES (7)',
    'invalid.sql': b'INVALID CONTRACT SQL',
}
package = SimpleNamespace(name='manifest_contract', manifest={
    'init_xml':[], 'data':['setup.sql', 'insert.sql', 'insert.sql'], 'demo':[]})
try:
    with mock.patch('tools.convert.file_open', side_effect=lambda path, mode: io.BytesIO(files[Path(path).name])):
        assert load_data({}, 'init', 'data', package, using='default')
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM contract_manifest_events')
            assert cursor.fetchone() == (2,)
        package.manifest['data'] = ['insert.sql', 'invalid.sql']
        try:
            with transaction.atomic(using='default'):
                load_data({}, 'update', 'data', package, using='default')
        except ProgrammingError:
            pass
        else:
            raise AssertionError('Invalid data must propagate to caller transaction')
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM contract_manifest_events')
            assert cursor.fetchone() == (2,)
finally:
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS contract_manifest_events')
result = {'pinned_differential_cases':len(cases), 'real_postgresql_sql_import':True,
          'duplicate_file_executed_twice':True,'caller_atomic_rolls_back_failed_data_stage':True,
          'reference_revision':'abe4040ec1a45beee90fb694e4eae4453e46b389',
          'limits':'Source-function differential, not native Odoo runtime; no XML/CSV/hooks/schema/registry/version acceptance'}
(Path(__file__).resolve().parents[1]/'outputs/manifest-data-postgresql.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
