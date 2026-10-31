"""Comparación temporal de Field.__set__ protegido; sin implementación ORM."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import os
import runpy
import secrets
import sys
import textwrap

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
os.environ['SECRET_KEY'] = secrets.token_urlsafe(40)
for prefix in ('DB_', 'DB_QA_'):
    for key, value in {'NAME': 'kaupamex_audit_only', 'USER': 'audit_only',
                       'PASSWORD': secrets.token_urlsafe(40), 'HOST': '127.0.0.1',
                       'PORT': '65432', 'SSL_MODE': 'disable', 'SOCKET': ''}.items():
        os.environ[prefix + key] = value

from django.db.backends.base.base import BaseDatabaseWrapper  # noqa: E402
attempts = []


def no_database(self):
    attempts.append(self.alias)
    raise AssertionError('No DB access authorized by this audit')


BaseDatabaseWrapper.ensure_connection = no_database
import django  # noqa: E402

django.setup()
from django.db import models  # noqa: E402
from orm.environments import env  # noqa: E402
from orm.models import BaseModel  # noqa: E402
from orm.fields import Char  # noqa: E402

sys.path.insert(0, 'scripts')
from reference_roots import require  # noqa: E402

extractor = runpy.run_path('scripts/workbench/basemodel-trae-contracts-20260911T050421/probes/extract_both_sides.py')
source = require() / 'odoo/orm/fields.py'
start, end, text = extractor['bodies'](source, {'Field'})['Field']['__set__'][0]
namespace = {}
exec(compile('from __future__ import annotations\n' + textwrap.dedent(text),
             str(source), 'exec'), namespace)


class AssignmentProbe(BaseModel):
    _name = 'audit.plain.assignment'
    label = Char(max_length=24)

    class Meta:
        app_label = 'base'
        managed = False


class ReferenceRecords:
    def __init__(self, environment, ids, prefetch):
        self.env = environment
        self._ids = ids
        self._prefetch_ids = prefetch


field = AssignmentProbe._meta.get_field('label')
records = AssignmentProbe._from_ids(env(), (7, 18), (7, 18))
field._insert_cache(records, ['old-7', 'old-18'])
reference_records = ReferenceRecords(SimpleNamespace(_protected={field: (7, 18)}),
                                     (7, 18), (7, 18))
calls = []


def observe_write(target, value):
    calls.append({'ids': list(target._ids), 'value': value})


with patch.object(field, 'write', observe_write):
    namespace['__set__'](field, reference_records, 'new')
    expected = list(calls)
    calls.clear()
    with env().protecting([field], records):
        records.label = 'new'
    actual = list(calls)
    calls.clear()
    field.write(records, 'control')
    control = list(calls)

result = {'contract': 'Field.__set__ dispatches protected plain-field assignment to write',
          'reference_source': 'odoo19c: odoo/orm/fields.py', 'reference_lines': [start, end],
          'reference_calls': expected, 'consumer_calls': actual, 'positive_witness_control': control,
          'consumer_field_cache': dict(field._get_cache(env())),
          'consumer_instance_attribute': records.label,
          'descriptor': type(vars(AssignmentProbe)['label']).__name__,
          'database_attempts': attempts,
          'scope': 'Protected branch only, actual original reference body; no persistent write or full ORM acceptance'}
assert expected == [{'ids': [7, 18], 'value': 'new'}]
assert control == [{'ids': [7, 18], 'value': 'control'}]
assert not attempts
result['contract_matches'] = actual == expected
# Reutiliza el extractor histórico; no ejecuta el runtime Odoo.
reference_env_source = require() / 'odoo/orm/environments.py'
get_start, get_end, get_text = extractor['bodies'](reference_env_source, {'Environment'})['Environment']['__getitem__'][0]
get_namespace = {}
exec(compile('from __future__ import annotations\n' + textwrap.dedent(get_text),
             str(reference_env_source), 'exec'), get_namespace)
reference_empty = get_namespace['__getitem__'](SimpleNamespace(registry={'res.partner': ReferenceRecords}), 'res.partner')
consumer_model = env()['res.partner']
result['environment_lookup'] = {'reference_ids': list(reference_empty._ids),
                                'reference_is_class': isinstance(reference_empty, type),
                                'consumer_is_class': isinstance(consumer_model, type),
                                'consumer_name': consumer_model.__name__,
                                'reference_lines': [get_start, get_end],
                                'same_representation': isinstance(reference_empty, type) == isinstance(consumer_model, type)}
assert reference_empty._ids == () and isinstance(consumer_model, type)
print(json.dumps(result, indent=2))
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
raise SystemExit(0 if result['contract_matches'] else 1)
