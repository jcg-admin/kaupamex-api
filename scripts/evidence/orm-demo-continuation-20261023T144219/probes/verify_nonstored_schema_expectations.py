"""Contrasta expectativas históricas sin cambiar propiedades ni aserciones."""
import ast
from collections import defaultdict
from copy import deepcopy
import __future__
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import django

django.setup()

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from counterpart_body import declarations_of
from reference_roots import tree
import fields
from addons.base.models import ResPartnerBank

reference = tree('odoo19c')
field_source = reference / 'odoo/orm/fields.py'
model_source = reference / 'odoo/orm/models.py'
sql_source = reference / 'odoo/tools/sql.py'
declarations = declarations_of(field_source)
constant = next(d for d in declarations_of(sql_source) if d.name == 'SQL_ORDER_BY_TYPE')
constant_namespace = {'defaultdict': defaultdict}
exec(compile(ast.Module(body=[constant.node], type_ignores=[]), str(sql_source),
             'exec'), constant_namespace)
table = constant_namespace['SQL_ORDER_BY_TYPE']
namespace = {'sql': SimpleNamespace(SQL_ORDER_BY_TYPE=table)}
for name in ('column_type', 'column_order'):
    declaration = next(d for d in declarations if d.owner == 'Field' and d.name == name)
    node = deepcopy(declaration.node)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(field_source),
                 'exec', flags=__future__.annotations.compiler_flag), namespace)

checks = []
for label, field in [
    ('unbound_nonstored_char', fields.Char(store=False)),
    ('unbound_stored_char', fields.Char()),
    ('bound_bank_name', ResPartnerBank._meta.get_field('bank_name')),
]:
    reference_type = namespace['column_type'](field)
    reference_order = namespace['column_order'](field)
    assert field.column_type == reference_type
    assert field.column_order == reference_order
    checks.append({
        'case': label, 'store': field.store, 'column': getattr(field, 'column', None),
        'consumer_type': field.column_type, 'reference_type': reference_type,
        'consumer_order': field.column_order, 'reference_order': reference_order,
    })

caller = next(d for d in declarations_of(model_source)
              if d.owner == 'BaseModel' and d.name == '_auto_init')
guards = [n.lineno for n in ast.walk(caller.node)
          if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp)
          and isinstance(n.test.op, ast.Not)
          and isinstance(n.test.operand, ast.Attribute)
          and n.test.operand.attr == 'store'
          and any(isinstance(statement, ast.Continue) for statement in n.body)]
assert guards
result = {
    'reference_revision': 'abe4040ec1a45beee90fb694e4eae4453e46b389',
    'command': 'uv run --frozen python probes/verify_nonstored_schema_expectations.py',
    'reference_hashes': {str(p.relative_to(reference)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (field_source, model_source, sql_source)},
    'checks': checks, 'native_caller_store_guard_lines': guards,
    'conclusion': 'These property results match pinned source. store=False alone does not make column_type None or column_order0; native schema caller skips nonstored fields before update_db.',
    'limits': 'Extracted property bodies/constant and caller AST only; not native Odoo runtime or whole schema workflow acceptance. Historical assertions retained; no TASK status or criteria changed.',
}
(Path(__file__).resolve().parents[1] / 'outputs/nonstored-schema-expectations.json').write_text(
    json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2), flush=True)
