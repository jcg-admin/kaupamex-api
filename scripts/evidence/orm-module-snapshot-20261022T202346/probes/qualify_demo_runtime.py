"""Existing demo dependencies: initialized registry, ambient scopes and PG atomic."""
import json
from pathlib import Path

import django

django.setup()

from django.conf import settings
from django.db import connection, transaction
from orm.environments import Environment, get_context, is_su
from orm.registry import Registry, MODELS_BY_NAME
from addons.base.models.ir_demo_failure import IrDemoFailure

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
registry = Registry('default')
env = Environment(cr='default', uid=42, su=False, context={'original': True})
try:
    canonical = env['ir.demo_failure'] is IrDemoFailure
except KeyError:
    canonical = False
assert env['base.IrDemoFailure'] is IrDemoFailure
before_su, before_context = is_su(), dict(get_context())
with connection.cursor() as cursor:
    cursor.execute('CREATE TEMP TABLE demo_qualification_events (value integer)')
with env:
    assert not is_su() and get_context() == {'original': True}
    try:
        with transaction.atomic(using='default'):
            with env(su=True, context={**env.context, 'install_demo': True}):
                assert is_su() and get_context()['install_demo']
                with connection.cursor() as cursor:
                    cursor.execute('INSERT INTO demo_qualification_events VALUES (1)')
                raise RuntimeError('Expected demo-stage rollback')
    except RuntimeError as error:
        assert str(error) == 'Expected demo-stage rollback'
    assert not is_su() and get_context() == {'original': True}
assert is_su() == before_su and dict(get_context()) == before_context
with connection.cursor() as cursor:
    cursor.execute('SELECT count(*) FROM demo_qualification_events')
    assert cursor.fetchone() == (0,)
    cursor.execute('DROP TABLE demo_qualification_events')
result = {'registry_constructed': registry.ready,
          'canonical_demo_failure_resolves': canonical,
          'django_label_demo_failure_resolves': True,
          'registered_names_after_initialization':[k for k,v in MODELS_BY_NAME.items() if v is IrDemoFailure],
          'elevation_context_activation_and_restoration':True,
          'real_pg_savepoint_rollback':True,
          'environment_get_method':hasattr(Environment,'get'),
          'remaining':'Real failure record persistence, long errors, optional todo resolution, selected-company alias/signal integration and whole demo stage remain not_verified',
          'acceptance':'Dependency qualification only; no implementation or TASK acceptance'}
(Path(__file__).resolve().parents[1]/'outputs/demo-initialized-qualification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
