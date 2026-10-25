"""Diagnostica precondiciones de los fixtures de caché sin alterar producción."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import django

django.setup()

ROOT = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-root', type=Path, required=True)
arguments = parser.parse_args()
sys.path.insert(0, str(ROOT / 'scripts'))
from counterpart_body import declarations_of
from orm.environments import env, transaction_scope

controls = runpy.run_path(str(ROOT / 'tests/unit/orm/test_field_conversion.py'))
model = controls['ConversionProbe']
field = controls['field_of']('label')
with transaction_scope():
    record = model(id=7)
    cache = field._get_cache_impl(env())
    constructor_populated = 7 in cache
    constructor_value = cache.get(7)
    cache[7] = 'de la cache'
    record.label = 'del atributo'
    after_assignment = cache[7]
    assert after_assignment == 'del atributo'
    assert field.get_column_update(record) == after_assignment
    cache[7] = 'cache posterior'
    assert field.get_column_update(record) == 'cache posterior'
    cache.pop(7)
    try:
        field.get_column_update(record)
    except KeyError:
        missing_raises = True
    else:
        raise AssertionError('Missing cache entry did not raise KeyError')

paths = [
    arguments.baseline_root / 'src/orm/fields.py',
    ROOT / 'src/orm/fields.py',
]
baseline_revision = subprocess.check_output(
    ['git', '-C', str(arguments.baseline_root), 'rev-parse', 'HEAD'], text=True,
).strip()
assert baseline_revision.startswith('ae949aa8')
assert paths[0].read_bytes() == subprocess.check_output(
    ['git', '-C', str(arguments.baseline_root), 'show', baseline_revision + ':src/orm/fields.py'],
)
bodies = []
for path in paths:
    declaration = next(d for d in declarations_of(path) if d.name == '_field_get_column_update')
    bodies.append(ast.dump(declaration.node, include_attributes=False))
assert bodies[0] == bodies[1]
result = {
    'constructor_populated_label_cache': constructor_populated,
    'constructor_value': constructor_value, 'after_normal_assignment': after_assignment,
    'later_cache_value_is_authoritative': True, 'explicit_absence_raises': missing_raises,
    'getter_body_unchanged_from_ae949aa8': True,
    'baseline_revision': baseline_revision,
    'getter_ast_sha256': hashlib.sha256(bodies[0].encode()).hexdigest(),
    'scope': 'Current unmanaged Django test model, existing transaction cache, no SQL. Not full constructor acceptance.',
}
(Path(__file__).resolve().parents[1] / 'outputs/schema-cache-fixture-diagnostics.json').write_text(
    json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2), flush=True)
