"""Six bounded flush_all protocol scenarios; no product or database imports.

The bridge deliberately models Odoo env[name] and Consumer model.objects.none()
as the same event endpoint. This tests orchestration, not actual ORM persistence.
"""
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import types


def consumer_root():
    declared = os.environ.get('THYROX_CONSUMER')
    for root in [Path(declared).resolve()] if declared else Path(__file__).resolve().parents:
        if (root / 'scripts/reference_roots.py').is_file():
            return root
    raise SystemExit('Set THYROX_CONSUMER to the API checkout')


API = consumer_root()
sys.path.insert(0, str(API / 'scripts'))
import reference_roots

EXTRACTOR = API / 'scripts/workbench/basemodel-trae-contracts-20260911T050421/probes/extract_both_sides.py'
spec = importlib.util.spec_from_file_location('historical_body_extractor', EXTRACTOR)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)
REFERENCE = reference_roots.require('odoo19c') / 'odoo/orm/environments.py'
CONSUMER = API / 'src/orm/environments.py'


def extracted(path):
    entries = extractor.bodies(path, {'Environment'})['Environment']['flush_all']
    assert len(entries) == 1
    start, end, source = entries[0]
    source = textwrap.dedent(source)
    tree = ast.parse(path.read_text())
    ceilings = [n.value.value for n in tree.body if isinstance(n, ast.Assign)
                and isinstance(n.value, ast.Constant)
                and any(isinstance(t, ast.Name) and t.id == 'MAX_FIXPOINT_ITERATIONS' for t in n.targets)]
    assert ceilings == [10]
    return {'path': str(path), 'start': start, 'end': end, 'body': source,
            'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'body_sha256': hashlib.sha256(source.encode()).hexdigest(), 'ceiling': ceilings[0]}


SOURCES = {'reference': extracted(REFERENCE), 'consumer': extracted(CONSUMER)}


class OrderedSetProtocol:
    def __init__(self, items=()):
        self._items = dict.fromkeys(items)
    def add(self, item):
        self._items[item] = None
    def __iter__(self):
        return iter(self._items)
    def __bool__(self):
        return bool(self._items)


class FieldProtocol:
    def __init__(self, name):
        self.model_name = name


class ModelProtocol:
    def __init__(self, environment, name):
        self.environment, self.name = environment, name
        self.objects = types.SimpleNamespace(none=lambda: self)
    def flush_model(self):
        env = self.environment
        env.events.append('flush:' + self.name)
        if env.scenario == 'flush_exception':
            raise RuntimeError('intentional-flush-model-error')
        if env.scenario != 'sticky_ceiling':
            for field in list(env._field_dirty):
                if field.model_name == self.name:
                    del env._field_dirty[field]
        if env.scenario == 'second_wave' and self.name == 'a' and not env.wave_added:
            env.wave_added = True
            env._field_dirty[env.fields['b']] = {2}


class EnvironmentProtocol:
    def __init__(self, scenario):
        self.scenario, self.events, self.warnings = scenario, [], []
        self.fields = {name: FieldProtocol(name) for name in ('a', 'a_alias', 'b')}
        self.fields['a_alias'].model_name = 'a'
        self.models = {name: ModelProtocol(self, name) for name in ('a', 'b')}
        self._field_dirty = {self.fields['a']: {1}}
        self.wave_added = False
        if scenario == 'multiple_models':
            self._field_dirty[self.fields['a_alias']] = {3}
            self._field_dirty[self.fields['b']] = {2}
        if scenario == 'empty_dirty_entry':
            self._field_dirty[self.fields['a']] = set()
    def __getitem__(self, name):
        return self.models[name]
    def _recompute_all(self):
        self.events.append('recompute')
        if self.scenario == 'recompute_exception':
            raise RuntimeError('intentional-recompute-error')
    def warning(self, message):
        self.warnings.append(message)


def observe(side, scenario, mutant=None):
    receiver = EnvironmentProtocol(scenario)
    namespace = {'MAX_FIXPOINT_ITERATIONS': SOURCES[side]['ceiling'],
                 'OrderedSet': OrderedSetProtocol, '_logger': receiver,
                 'registry': object(),
                 'model_of_field': lambda field, registry: receiver.models[field.model_name]}
    source = SOURCES[side]['body']
    if mutant == 'omit_recompute':
        source = source.replace('self._recompute_all()', 'pass', 1)
    elif mutant == 'omit_warning':
        source = source.replace('_logger.warning("Too many iterations for flushing fields!")', 'pass', 1)
    exec(compile(source, SOURCES[side]['path'], 'exec'), namespace)
    try:
        result = namespace['flush_all'](receiver)
        exception = None
    except RuntimeError as error:
        result, exception = None, str(error)
    return {'events': receiver.events, 'warnings': receiver.warnings,
            'exception': exception, 'return': result,
            'remaining_dirty_entries': len(receiver._field_dirty)}


CASES = {scenario: {side: observe(side, scenario) for side in ('reference', 'consumer')}
         for scenario in ('multiple_models', 'second_wave', 'recompute_exception',
                          'flush_exception', 'sticky_ceiling', 'empty_dirty_entry')}
for scenario in ('multiple_models', 'second_wave', 'recompute_exception', 'flush_exception', 'sticky_ceiling'):
    assert CASES[scenario]['reference'] == CASES[scenario]['consumer']
assert CASES['multiple_models']['reference']['events'] == ['recompute', 'flush:a', 'flush:b', 'recompute']
assert CASES['second_wave']['reference']['events'] == ['recompute', 'flush:a', 'recompute', 'flush:b', 'recompute']
assert CASES['recompute_exception']['reference']['events'] == ['recompute']
assert CASES['recompute_exception']['reference']['exception'] == 'intentional-recompute-error'
assert CASES['flush_exception']['reference']['events'] == ['recompute', 'flush:a']
assert CASES['flush_exception']['reference']['exception'] == 'intentional-flush-model-error'
assert CASES['sticky_ceiling']['reference']['events'] == ['recompute', 'flush:a'] * 10
assert CASES['sticky_ceiling']['reference']['warnings'] == ['Too many iterations for flushing fields!']
assert CASES['sticky_ceiling']['reference']['remaining_dirty_entries'] == 1
assert CASES['empty_dirty_entry']['reference']['events'] == ['recompute', 'flush:a', 'recompute']
assert CASES['empty_dirty_entry']['consumer']['events'] == ['recompute']
assert CASES['empty_dirty_entry']['consumer']['remaining_dirty_entries'] == 1
assert observe('reference', 'multiple_models', 'omit_recompute') != CASES['multiple_models']['reference']
assert observe('reference', 'sticky_ceiling', 'omit_warning') != CASES['sticky_ceiling']['reference']

report = {
    'reference_revision': 'abe4040ec1a45beee90fb694e4eae4453e46b389',
    'consumer_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=API, text=True).strip(),
    'dependencies': {'python': sys.version.split()[0], 'Django_distribution': importlib.metadata.version('Django')},
    'extractor': str(EXTRACTOR.relative_to(API)),
    'extractor_sha256': hashlib.sha256(EXTRACTOR.read_bytes()).hexdigest(),
    'sources': SOURCES, 'cases': CASES,
    'negative_controls': {'omitting_recompute_detected': True, 'omitting_ceiling_warning_detected': True},
    'result': 'Five orchestration protocols agree; the existing documented empty-dirty-entry normalization differs as expected.',
    'scope': 'Exact flush_all bodies on a declared OrderedSet/in-memory model bridge, no Django setup and no DB.',
    'not_verified': ['Real OrderedSet implementation', 'Actual model resolver', 'Recompute implementation',
                     'Dirty cache persistence and PostgreSQL writes', 'Exception rollback cleanup',
                     'Stored/nonstored field families', 'Actual Odoo runtime tests', 'Acceptance of the empty-entry representation adaptation'],
    'reproduction': 'THYROX_CONSUMER=<API> ODOO_TOOLS=<verified reference> UV_CACHE_DIR=<cache> uv run --frozen python <probe_flush_fixpoint.py>',
}
destination = Path(__file__).with_name('flush-fixpoint-observations.json')
destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'cases': CASES, 'negative_controls': report['negative_controls'], 'evidence': str(destination)}, indent=2))
