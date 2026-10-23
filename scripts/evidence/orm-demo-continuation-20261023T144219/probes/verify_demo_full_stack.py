"""Actual migrated DB, models, files, converter and signals; no mocked backend."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import django

django.setup()

from django.conf import settings
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from addons.base.models.ir_actions import IrActionsActions, IrActionsTodo
from addons.base.models.ir_demo_failure import IrDemoFailure
from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModule
from modules.loading import load_demo
from orm.environments import Environment, get_context, is_su
from orm.registry import Registry

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
assert ('base','0089_demo_failure_error_length') in MigrationRecorder(connection).applied_migrations()
root = Path(__file__).resolve().parents[4]
Registry('default')
env = Environment(cr='default', uid=42, su=False, context={'verification':True})
before = (is_su(), dict(get_context()))
with TemporaryDirectory(prefix='demo_contract_', dir=root/'addons') as directory:
    path = Path(directory)
    module = IrModule.objects.create(name=path.name, state='to install', version='19.0.1')
    action = IrActionsActions.objects.create(name='Demo contract action', type='ir.actions.act_window_close')
    configuration_step = IrActionsTodo.objects.create(action=action, name='Demo contract todo', state='done')
    IrModelData.objects.update_or_create(module='base', name='demo_failure_todo', defaults={
        'model':'base.IrActionsTodo', 'res_id':configuration_step.pk, 'noupdate':True})
    (path/'insert.sql').write_text('INSERT INTO contract_demo_runtime_events VALUES (1);')
    (path/'failure.sql').write_text("SELECT CAST(repeat('original-demo-error Ω',400) AS integer);")
    (path/'success.sql').write_text('INSERT INTO contract_demo_runtime_events VALUES (2);')
    package = SimpleNamespace(name=path.name, id=module.pk,
        manifest={'demo':['insert.sql','failure.sql']})
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE contract_demo_runtime_events (value integer)')
        cursor.execute('INSERT INTO contract_demo_runtime_events VALUES (10)')
    try:
        with transaction.atomic():
            assert load_demo(env, package, {}, 'init') is False
            with connection.cursor() as cursor:
                cursor.execute('SELECT value FROM contract_demo_runtime_events ORDER BY value')
                assert cursor.fetchall() == [(10,)]
            configuration_step.refresh_from_db()
            assert configuration_step.state == 'open'
            failure = IrDemoFailure.objects.get(module=module)
            assert len(failure.error) > 255
            assert 'original-demo-error Ω' in failure.error
            assert 'Traceback' in failure.error
            (Path(__file__).resolve().parents[1]/'outputs/demo-original-error.txt').write_text(failure.error)
            package.manifest['demo'] = ['success.sql']
            assert load_demo(env, package, {}, 'init') is True
            with connection.cursor() as cursor:
                cursor.execute('SELECT value FROM contract_demo_runtime_events ORDER BY value')
                assert cursor.fetchall() == [(2,),(10,)]
            module.refresh_from_db()
            assert module.state == 'to install' and module.installed_version is None
            assert IrDemoFailure.objects.filter(module=module).count() == 1
        assert (is_su(), dict(get_context())) == before
        results = {'real_migrated_postgresql':True,'real_files_and_converter':True,
                   'real_todo_xmlid_and_failure_models':True,'automation_signals_not_mocked':True,
                   'failed_demo_data_rolled_back':True,'success_data_retained_by_caller_transaction':True,
                   'error_length':len(failure.error),'error_sha256':hashlib.sha256(failure.error.encode()).hexdigest(),
                   'todo_open':True,'context_restored':True,'module_state_and_installed_version_not_finalized':True,
                   'limits':'N=1 existing default installation only; per-company full migration, XML/CSV/hooks/registry composition and whole TASK acceptance remain separate'}
    finally:
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE contract_demo_runtime_events')
(Path(__file__).resolve().parents[1]/'outputs/demo-full-stack.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
