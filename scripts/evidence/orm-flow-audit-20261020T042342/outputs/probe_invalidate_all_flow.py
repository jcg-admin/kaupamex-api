"""Bounded differential call-order probe; no Django setup or database access.

Bodies are extracted through the existing historical extractor. Protocol
receivers observe calls and exception propagation, not ORM persistence.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import textwrap

def consumer_root():
    declared = os.environ.get('THYROX_CONSUMER')
    if declared:
        root = Path(declared).resolve()
        if (root / 'scripts/reference_roots.py').is_file():
            return root
        raise SystemExit('THYROX_CONSUMER does not contain scripts/reference_roots.py')
    for root in Path(__file__).resolve().parents:
        if (root / 'scripts/reference_roots.py').is_file():
            return root
    raise SystemExit('Set THYROX_CONSUMER to the API checkout for an external probe path')

API = consumer_root()
sys.path.insert(0, str(API / 'scripts'))
import reference_roots

extractor_path = API / 'scripts/workbench/basemodel-trae-contracts-20260911T050421/probes/extract_both_sides.py'
spec = importlib.util.spec_from_file_location('historical_body_extractor', extractor_path)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)

reference_path = reference_roots.require('odoo19c') / 'odoo/orm/environments.py'
consumer_path = API / 'src/orm/environments.py'

def extracted(path):
    entries = extractor.bodies(path, {'Environment'})['Environment']['invalidate_all']
    assert len(entries) == 1
    start, end, body = entries[0]
    source = textwrap.dedent(body)
    namespace = {}
    exec(compile(source, str(path), 'exec'), namespace)
    return namespace['invalidate_all'], {
        'path': str(path), 'start': start, 'end': end,
        'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'body_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'body': source,
    }

reference, reference_source = extracted(reference_path)
consumer, consumer_source = extracted(consumer_path)

class TransactionProbe:
    def __init__(self, events):
        self.events = events
    def invalidate_field_data(self):
        self.events.append('invalidate_field_data')

class EnvironmentProbe:
    def __init__(self, fail_flush=False):
        self.events = []
        self.transaction = TransactionProbe(self.events)
        self.fail_flush = fail_flush
    def flush_all(self):
        self.events.append('flush_all')
        if self.fail_flush:
            raise RuntimeError('intentional-flush-failure')

def observe(function, kwargs, fail_flush=False):
    receiver = EnvironmentProbe(fail_flush)
    try:
        result = function(receiver, **kwargs)
        exception = None
    except RuntimeError as error:
        result = None
        exception = str(error)
    return {'events': receiver.events, 'return': result, 'exception': exception}

cases = {}
for name, kwargs, fail_flush in (
    ('default_flush', {}, False),
    ('explicit_true', {'flush': True}, False),
    ('explicit_false', {'flush': False}, False),
    ('flush_failure', {}, True),
):
    left, right = observe(reference, kwargs, fail_flush), observe(consumer, kwargs, fail_flush)
    cases[name] = {'reference': left, 'consumer': right, 'equivalent_observation': left == right}

assert cases['default_flush']['reference']['events'] == ['flush_all', 'invalidate_field_data']
assert cases['default_flush']['consumer']['events'] == ['invalidate_field_data']
assert cases['explicit_true']['equivalent_observation'] is False
assert cases['explicit_false']['equivalent_observation'] is True
assert cases['flush_failure']['reference'] == {
    'events': ['flush_all'], 'return': None, 'exception': 'intentional-flush-failure'}
assert cases['flush_failure']['consumer'] == {
    'events': ['invalidate_field_data'], 'return': None, 'exception': None}

# A controlled in-memory mutant removes the actual reference guard's call.
# The oracle must reject it for default=True, while flush=False stays a
# positive control. No source file or operational taxonomy is changed.
mutant_source = reference_source['body'].replace('self.flush_all()', 'pass', 1)
assert mutant_source != reference_source['body']
mutant_namespace = {}
exec(compile(mutant_source, '<in-memory-reference-mutant>', 'exec'), mutant_namespace)
mutant = mutant_namespace['invalidate_all']
assert observe(mutant, {}) != observe(reference, {})
assert observe(mutant, {'flush': False}) == observe(reference, {'flush': False})

report = {
    'question': 'Does actual Environment.invalidate_all preserve flush-before-invalidate and flush exception propagation?',
    'reference_revision': 'abe4040ec1a45beee90fb694e4eae4453e46b389',
    'consumer_revision': '694587d9a5b6715e1e0309e7c8b36c58d8ebdc2d',
    'sources': {'reference': reference_source, 'consumer': consumer_source,
                'extractor_sha256': hashlib.sha256(extractor_path.read_bytes()).hexdigest()},
    'observations': cases,
    'negative_control': 'Removing reference flush call is detected under default=True; explicit False still agrees.',
    'result': 'Observed contractual call-order/exception gap; test assertions pass by proving the gap.',
    'scope': 'Exact extracted method bodies, protocol receivers; no imports of Consumer Django modules and no DB connection.',
    'not_verified': ['Actual PostgreSQL dirty-data persistence/loss', 'Full Environment lifecycle',
                     'Reference test suite', 'Application consumers and their transactions',
                     'TASK eligibility and acceptance'],
}
destination = Path(__file__).with_name('invalidate-all-observations.json')
destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'cases': cases, 'negative_control_detected': True, 'evidence': str(destination)}, indent=2))
