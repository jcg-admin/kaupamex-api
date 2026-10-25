"""Verifica invalidación persistida y mide la lectura escalar sin SQL."""
import argparse
import hashlib
import json
import statistics
import timeit
from pathlib import Path

import django
from django.db import connection, transaction
from django.db.models.query_utils import DeferredAttribute
from django.test.utils import CaptureQueriesContext

django.setup()

from addons.base.models.ir_config_parameter import SystemParameter
from orm.environments import env, transaction_scope
from orm.registry import field_depends


parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not connection.settings_dict['NAME'].startswith('orm_bootstrap_'):
    raise SystemExit('Se requiere la base propia del harness existente.')

with transaction.atomic(), transaction_scope():
    row = SystemParameter.objects.create(key='fixture.dependencies.before', value='x')
    field = row._meta.get_field('display_name')
    result = {'dependencies': list(field_depends[field]), 'first': row.display_name}
    descriptor = type(row).__dict__['key']
    with CaptureQueriesContext(connection) as queries:
        current = timeit.repeat('row.key', globals={'row': row}, number=100_000, repeat=3)
        try:
            # Equivale al camino caliente anterior: un descriptor sin setter
            # cede a __dict__ y su cuerpo nunca se ejecuta en esta lectura.
            setattr(type(row), 'key', DeferredAttribute(row._meta.get_field('key')))
            baseline = timeit.repeat('row.key', globals={'row': row}, number=100_000, repeat=3)
        finally:
            setattr(type(row), 'key', descriptor)
    result['scalar_read_measurement'] = {
        'iterations_per_sample': 100_000, 'samples': 3,
        'current_seconds': current, 'non_data_baseline_seconds': baseline,
        'current_median_ns': statistics.median(current) * 10_000,
        'baseline_median_ns': statistics.median(baseline) * 10_000,
        'sql_queries': len(queries),
        'limit': 'Lectura escalar en proceso aislado; no mide rendimiento de la aplicación.',
    }
    row.key = 'fixture.dependencies.after'
    result['cache_absent_after_assignment'] = row.pk not in field._get_cache(env())
    result['instance_snapshot_after_assignment'] = row.__dict__.get('display_name')
    result['read_after_assignment'] = row.display_name
    row.save(update_fields=['key'])
    result['read_after_save'] = row.display_name
    result['stored_key'] = SystemParameter.objects.filter(pk=row.pk).values_list('key', flat=True).get()
    transaction.set_rollback(True)

result['source_sha256'] = {
    str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in map(Path, (
        'src/orm/fields.py', 'src/orm/models.py',
        'src/addons/base/models/res_partner.py',
    ))
}
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
if (not result['cache_absent_after_assignment']
        or result['read_after_assignment'] != 'fixture.dependencies.after'
        or result['read_after_save'] != result['stored_key']):
    raise SystemExit(1)
