"""Pinned name-check differential against isolated actual PostgreSQL catalogues."""
import __future__
import ast
import json
import logging
from pathlib import Path
import sys
from unittest import mock

import django

django.setup()

from django.conf import settings
from django.db import connection
from django.db.migrations.state import ModelState, ProjectState

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from counterpart_body import declarations_of
from reference_roots import tree
from addons.base.models.ir_module import IrModule, IrModuleCategory
from modules import loading

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
source = tree('odoo19c')/'odoo/modules/loading.py'
declaration = next(d for d in declarations_of(source)
                   if d.kind == 'function' and d.name == '_check_module_names')
namespace = {'_logger': logging.getLogger('pinned_loading_names')}
exec(compile(ast.Module(body=[declaration.node], type_ignores=[]), str(source),
             'exec', flags=__future__.annotations.compiler_flag), namespace)
reference = namespace['_check_module_names']
consumer = (lambda cursor, names: None) if '--annul-validation' in sys.argv else loading._check_module_names


class ReferenceCursor:
    """Adapt dictfetchall and psycopg2 tuple expansion to psycopg3 arrays."""
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, parameters=None):
        if 'name in %s' in query:
            query = query.replace('name in %s', 'name = ANY(%s)')
            parameters = (list(parameters[0]),)
        return self.cursor.execute(query, parameters)

    def fetchone(self):
        return self.cursor.fetchone()

    def dictfetchall(self):
        return [{'name': name} for name, in self.cursor.fetchall()]


state = ProjectState()
state.add_model(ModelState.from_model(IrModuleCategory))
state.add_model(ModelState.from_model(IrModule))
category = state.apps.get_model('base', 'IrModuleCategory')
module = state.apps.get_model('base', 'IrModule')
schemas = ('contract_names_first', 'contract_names_second')
checks = []
try:
    for schema, installed in zip(schemas, ('sale', 'stock')):
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA {schema}')
            cursor.execute(f'SET search_path TO {schema}')
        with connection.schema_editor() as editor:
            editor.create_model(category)
            editor.create_model(module)
        module.objects.create(name='base', state='installed')
        module.objects.create(name=installed, state='to install')
        before = list(module.objects.order_by('name').values_list('name', 'state'))
        cases = [[], ['all'], ['base', 'base', 'all'], [installed],
                 ['sale'], ['stock'], ['unknown_contract', 'base'],
                 ["unknown'); DROP TABLE ir_module_module; --"]]
        for names in cases:
            messages = []
            for function, logger in [(reference, namespace['_logger']),
                                     (consumer, loading._logger)]:
                with connection.cursor() as cursor, mock.patch.object(logger, 'warning') as warning:
                    assert function(ReferenceCursor(cursor) if function is reference else cursor,
                                    (name for name in names)) is None
                    messages.append([call.args[0] % call.args[1:]
                                     for call in warning.call_args_list])
            assert messages[0] == messages[1], (schema, names, messages)
            checks.append({'schema': schema, 'requested': names, 'warnings': messages[1]})
        assert list(module.objects.order_by('name').values_list('name', 'state')) == before
    print(json.dumps({'postgresql_catalogue_cases': checks, 'states_unchanged': True,
                      'scope': 'Two isolated schemas in one owned database; not productive multi-database acceptance'}, indent=2))
finally:
    with connection.cursor() as cursor:
        cursor.execute('SET search_path TO public')
        for schema in schemas:
            cursor.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
