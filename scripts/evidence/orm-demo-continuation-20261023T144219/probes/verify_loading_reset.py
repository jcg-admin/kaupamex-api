"""Actual PostgreSQL recovery, failure atomicity and pinned-source comparison."""
import __future__
import ast
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace

import django

django.setup()

from django.conf import settings
from django.db import connection, IntegrityError, transaction
from django.db.migrations.state import ModelState, ProjectState
from django.db.transaction import TransactionManagementError

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from counterpart_body import declarations_of
from reference_roots import tree
from addons.base.models.ir_module import IrModule
from modules.loading import reset_modules_state

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
recover = (lambda alias: None) if '--annul-reset' in sys.argv else reset_modules_state
assert recover('default') is None  # No catalogue on this fresh owned database.
assert 'ir_module_module' not in connection.introspection.table_names()
state = ProjectState()
state.add_model(ModelState.from_model(IrModule))
module = state.apps.get_model('base', 'IrModule')
states = ('installed', 'uninstalled', 'uninstallable', 'to install', 'to upgrade', 'to remove')
expected = ('installed', 'uninstalled', 'uninstallable', 'uninstalled', 'installed', 'installed')


def snapshot():
    return list(module.objects.order_by('id').values_list('state', 'installed_version'))


source = tree('odoo19c')/'odoo/modules/loading.py'
declaration = next(d for d in declarations_of(source)
                   if d.kind == 'function' and d.name == 'reset_modules_state')
namespace = {'_logger': logging.getLogger('pinned_loading_reset'),
             'odoo': SimpleNamespace(
                 sql_db=SimpleNamespace(db_connect=lambda name: connection),
                 tools=SimpleNamespace(sql=SimpleNamespace(table_exists=
                     lambda cursor, table: table in connection.introspection.table_names(cursor))))}
exec(compile(ast.Module(body=[declaration.node], type_ignores=[]), str(source),
             'exec', flags=__future__.annotations.compiler_flag), namespace)
with connection.schema_editor() as editor:
    editor.create_model(module)
try:
    for index, status in enumerate(states):
        module.objects.create(name=f'recovery_contract_{index}', state=status,
                              installed_version='19.0.1')
    initial = snapshot()
    # The second UPDATE fails after the first has executed. Neither may persist.
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE ir_module_module ADD CONSTRAINT contract_recovery_guard "
                       "CHECK (state <> 'uninstalled') NOT VALID")
    try:
        try:
            recover('default')
        except IntegrityError:
            pass
        else:
            raise AssertionError('Second-update SQL failure must propagate')
        assert snapshot() == initial, 'First update escaped recovery rollback'
    finally:
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE ir_module_module DROP CONSTRAINT contract_recovery_guard')
    with transaction.atomic():
        try:
            recover('default')
        except TransactionManagementError:
            pass
        else:
            raise AssertionError('Recovery must refuse a caller-owned transaction')
        assert snapshot() == initial
    namespace['reset_modules_state']('default')
    reference_result = snapshot()
    with connection.cursor() as cursor:
        for index, status in enumerate(states):
            cursor.execute('UPDATE ir_module_module SET state=%s WHERE name=%s',
                           [status, f'recovery_contract_{index}'])
    recover('default')
    assert snapshot() == reference_result == [(status, '19.0.1') for status in expected]
    independent = connection.copy()
    try:
        with independent.cursor() as cursor:
            cursor.execute('SELECT state,installed_version FROM ir_module_module ORDER BY id')
            assert cursor.fetchall() == reference_result
    finally:
        independent.close()
    print(json.dumps({'actual_postgresql': True, 'source_differential': True,
                      'states': dict(zip(states, expected)), 'version_preserved': True,
                      'committed_visible_from_independent_connection': True,
                      'second_update_failure_rolls_back_both': True,
                      'missing_table_noop': True, 'nested_transaction_refused': True,
                      'limits': 'Bounded recovery stage, no outer-loader caller integration or TASK acceptance'}, indent=2))
finally:
    with connection.schema_editor() as editor:
        editor.delete_model(module)
