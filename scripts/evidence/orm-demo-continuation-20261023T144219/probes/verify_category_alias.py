"""Verifica el alias del árbol con PostgreSQL y bloqueo de fallback a default."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from unittest import mock
import uuid

import django

django.setup()

from django.conf import settings
from django.db import connection, connections

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModuleCategory
from modules.db import create_categories


parser = argparse.ArgumentParser()
parser.add_argument('--result', type=Path, required=True)
arguments = parser.parse_args()
assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
alias = 'category_contract_alias'
assert alias not in connections.databases
schema = 'contract_category_alias_' + uuid.uuid4().hex[:12]
configuration = deepcopy(settings.DATABASES['default'])
configuration['OPTIONS'] = {
    **configuration.get('OPTIONS', {}), 'options': f'-c search_path={schema}',
}
result = {
    'alias': alias, 'schema': schema, 'passed': False,
    'scope': 'Separate connection and namespace in one owned physical database; not N>1 acceptance',
    'mechanism': 'Existing create_categories, Django execute_wrapper and schema_editor; no private DB-blocker override',
}


def reject_default_tree_access(execute, sql, params, many, context):
    if 'ir_module_category' in sql.lower() or 'ir_model_data' in sql.lower():
        raise AssertionError('Category helper accessed default instead of its cursor alias')
    return execute(sql, params, many, context)


with connection.cursor() as cursor:
    cursor.execute(f'CREATE SCHEMA {connection.ops.quote_name(schema)}')
try:
    before = (IrModuleCategory.objects.count(), IrModelData.objects.count())
    with mock.patch.dict(settings.DATABASES, {alias: configuration}):
        connections.databases[alias] = configuration
        database = connections[alias]
        try:
            with database.schema_editor() as editor:
                editor.create_model(IrModuleCategory)
                editor.create_model(IrModelData)
            with connection.execute_wrapper(reject_default_tree_access):
                with database.cursor() as cursor:
                    leaf = create_categories(cursor, ['Alias Root', 'Child', 'Leaf'])
                    assert create_categories(cursor, ['Alias Root', 'Child', 'Leaf']) == leaf
                    sibling = create_categories(cursor, ['Alias Root', 'Child', 'Second'])
                    assert sibling != leaf
            assert IrModuleCategory.objects.using(alias).count() == 4
            assert IrModelData.objects.using(alias).count() == 4
            assert IrModuleCategory.objects.using(alias).filter(pk=leaf).values_list(
                'parent__parent__name', flat=True,
            ).get() == 'Alias Root'
        finally:
            database.close()
            del connections[alias]
            connections.databases.pop(alias, None)
    assert (IrModuleCategory.objects.count(), IrModelData.objects.count()) == before
    result['passed'] = True
finally:
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SCHEMA {connection.ops.quote_name(schema)} CASCADE')
    result['schema_cleanup'] = True
    arguments.result.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
