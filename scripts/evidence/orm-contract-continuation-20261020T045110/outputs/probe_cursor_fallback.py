"""Actual Registry.cursor bodies on isolated deterministic protocols.

No Django setup, databases, live clocks, threads, or product mutation.  The
historical extractor supplies both method bodies; the reference cooldown is
read from the exact reference AST, without a second function-body extractor.
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
    candidates = [Path(declared).resolve()] if declared else Path(__file__).resolve().parents
    for candidate in candidates:
        if (candidate / 'scripts/reference_roots.py').is_file():
            return candidate
    raise SystemExit('Set THYROX_CONSUMER to an API checkout containing scripts/reference_roots.py')


API = consumer_root()
sys.path.insert(0, str(API / 'scripts'))
import reference_roots
from django.db import DatabaseError, OperationalError, ProgrammingError

# The Consumer does not install the complete Odoo runtime (psycopg2).  These
# isolated protocol classes exercise only the actual body's except branch;
# they do not establish PostgreSQL or psycopg2 exception compatibility.
ReferenceDatabaseError = type('DatabaseError', (Exception,), {})
ReferenceOperationalError = type('OperationalError', (ReferenceDatabaseError,), {})
ReferenceProgrammingError = type('ProgrammingError', (ReferenceDatabaseError,), {})
reference_exception_protocol = types.SimpleNamespace(
    DatabaseError=ReferenceDatabaseError,
    OperationalError=ReferenceOperationalError,
    ProgrammingError=ReferenceProgrammingError)

EXTRACTOR = API / 'scripts/workbench/basemodel-trae-contracts-20260911T050421/probes/extract_both_sides.py'
spec = importlib.util.spec_from_file_location('historical_body_extractor', EXTRACTOR)
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)
REFERENCE = reference_roots.require('odoo19c') / 'odoo/orm/registry.py'
CONSUMER = API / 'src/orm/registry.py'
reference_tree = ast.parse(REFERENCE.read_text())
retry_nodes = [n.value for n in reference_tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == '_REPLICA_RETRY_TIME' for t in n.targets)]
assert len(retry_nodes) == 1
# Only the bounded constant expression from the verified source is evaluated.
RETRY = eval(compile(ast.Expression(retry_nodes[0]), str(REFERENCE), 'eval'), {'__builtins__': {}})
assert RETRY == 1200


def body(path):
    entries = extractor.bodies(path, {'Registry'})['Registry']['cursor']
    assert len(entries) == 1
    start, end, text = entries[0]
    source = textwrap.dedent(text)
    return {'path': str(path), 'start': start, 'end': end, 'body': source,
            'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'body_sha256': hashlib.sha256(source.encode()).hexdigest()}


SOURCES = {'reference': body(REFERENCE), 'consumer': body(CONSUMER)}


class Clock:
    def __init__(self):
        self.now = 100.0
    def monotonic(self):
        return self.now


class Logger:
    def __init__(self):
        self.messages = []
    def warning(self, message, *args):
        self.messages.append(message % args)


class Endpoint:
    def __init__(self, label, responses, exceptions):
        self.label = label
        self.responses = iter(responses)
        self.exceptions = exceptions
        self.attempts = 0
    def cursor(self):
        self.attempts += 1
        response = next(self.responses, 'ok')
        if response != 'ok':
            raise self.exceptions[response](f'{self.label}:{response}')
        return f'{self.label}-cursor'


class Harness:
    def __init__(self, side, responses=(), primary_responses=(), present=True, mutant=None):
        self.side = side
        self.clock = Clock()
        self.thread = types.SimpleNamespace()
        self.logger = Logger()
        exceptions = ({'operational': ReferenceOperationalError, 'programming': ReferenceProgrammingError}
                      if side == 'reference' else
                      {'operational': OperationalError, 'programming': ProgrammingError})
        self.primary = Endpoint('primary', primary_responses, exceptions)
        self.replica = Endpoint('replica', responses, exceptions)
        self.receiver = types.SimpleNamespace(
            _db=self.primary, _db_readonly=self.replica if present else None,
            _db_readonly_failed_time=None, _alias=lambda: 'default')
        connections = {'default': self.primary}
        if present:
            connections['default_readonly'] = self.replica
        namespace = {'BaseCursor': object, 'time': self.clock,
                     'threading': types.SimpleNamespace(current_thread=lambda: self.thread),
                     'psycopg2': reference_exception_protocol, '_logger': self.logger,
                     '_REPLICA_RETRY_TIME': RETRY, 'connections': connections,
                     'DatabaseError': DatabaseError}
        source = SOURCES[side]['body']
        if mutant == 'no_cooldown':
            source = source.replace('_REPLICA_RETRY_TIME', '0')
        elif mutant == 'broad_error':
            source = source.replace('except psycopg2.OperationalError:', 'except psycopg2.DatabaseError:')
        exec(compile(source, SOURCES[side]['path'], 'exec'), namespace)
        self.function = namespace['cursor']
    def call(self, readonly=True, at=None):
        if at is not None:
            self.clock.now = at
        try:
            returned = self.function(self.receiver, readonly=readonly)
            error = None
        except Exception as exception:
            returned = None
            error = {'class': type(exception).__name__, 'message': str(exception)}
        return {'time': self.clock.now, 'returned': returned, 'error': error,
                'primary_attempts': self.primary.attempts, 'replica_attempts': self.replica.attempts,
                'failed_time': self.receiver._db_readonly_failed_time,
                'thread_cursor_mode': getattr(self.thread, 'cursor_mode', None),
                'warning_count': len(self.logger.messages)}


CASES = {}
for name, params, calls in (
    ('writable_bypasses_replica', {'responses': ['operational']}, [{'readonly': False}]),
    ('readonly_no_replica', {'present': False}, [{}]),
    ('replica_success', {'responses': ['ok']}, [{}]),
    ('operational_then_retry', {'responses': ['operational', 'ok']},
     [{'at': 100.0}, {'at': 101.0}, {'at': 1300.0}, {'at': 1300.001}]),
    ('programming_error', {'responses': ['programming']}, [{}]),
    ('primary_error', {'present': False, 'primary_responses': ['operational']}, [{}]),
):
    observed = {}
    for side in ('reference', 'consumer'):
        harness = Harness(side, **params)
        observed[side] = [harness.call(**call) for call in calls]
    CASES[name] = observed

for name in ('writable_bypasses_replica', 'readonly_no_replica'):
    for side in ('reference', 'consumer'):
        assert CASES[name][side][0]['returned'] == 'primary-cursor'
        assert CASES[name][side][0]['replica_attempts'] == 0
        assert CASES[name][side][0]['thread_cursor_mode'] is None
for side in ('reference', 'consumer'):
    assert CASES['replica_success'][side][0]['returned'] == 'replica-cursor'
    assert CASES['replica_success'][side][0]['primary_attempts'] == 0
    assert CASES['primary_error'][side][0]['error']['class'] == 'OperationalError'
    assert CASES['primary_error'][side][0]['returned'] is None

timeline = CASES['operational_then_retry']
assert [item['replica_attempts'] for item in timeline['reference']] == [1, 1, 1, 2]
assert [item['returned'] for item in timeline['reference']] == [
    'primary-cursor', 'primary-cursor', 'primary-cursor', 'replica-cursor']
assert [item['replica_attempts'] for item in timeline['consumer']] == [1, 2, 3, 4]
assert [item['returned'] for item in timeline['consumer']] == [
    'primary-cursor', 'replica-cursor', 'replica-cursor', 'replica-cursor']
assert timeline['reference'][0]['failed_time'] == 100.0
assert timeline['reference'][-1]['failed_time'] is None
assert all(item['thread_cursor_mode'] == 'ro->rw' for item in timeline['reference'])
assert all(item['thread_cursor_mode'] is None for item in timeline['consumer'])
assert CASES['programming_error']['reference'][0]['error']['class'] == 'ProgrammingError'
assert CASES['programming_error']['reference'][0]['primary_attempts'] == 0
assert CASES['programming_error']['consumer'][0]['returned'] == 'primary-cursor'
assert CASES['programming_error']['consumer'][0]['error'] is None

mutant = Harness('reference', responses=['operational', 'ok'], mutant='no_cooldown')
mutant.call(at=100.0)
mutant_retry = mutant.call(at=101.0)
assert mutant_retry['replica_attempts'] == 2
assert mutant_retry['returned'] != timeline['reference'][1]['returned']
mutant_error = Harness('reference', responses=['programming'], mutant='broad_error').call()
assert mutant_error['error'] is None
assert mutant_error['returned'] == 'primary-cursor'

report = {
    'reference_revision': 'abe4040ec1a45beee90fb694e4eae4453e46b389',
    'consumer_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=API, text=True).strip(),
    'extractor': str(EXTRACTOR.relative_to(API)),
    'extractor_sha256': hashlib.sha256(EXTRACTOR.read_bytes()).hexdigest(),
    'dependencies': {'python': sys.version.split()[0], 'django': importlib.metadata.version('Django'),
                     'psycopg': importlib.metadata.version('psycopg'),
                     'reference_exception_protocol': 'Isolated DatabaseError/OperationalError/ProgrammingError classes; psycopg2 runtime is not installed.'},
    'retry_seconds_from_reference': RETRY, 'sources': SOURCES, 'cases': CASES,
    'negative_controls': {'cooldown_removed_detected': True, 'exception_broadened_detected': True},
    'scope': 'Exact extracted Registry.cursor bodies with deterministic endpoints, clock, logger, thread protocols; real Consumer Django exception classes and explicitly isolated reference exception protocol.',
    'result': 'Differences characterized for retry suppression, failure timestamp/thread mode, and error propagation. Shared positive branches agree.',
    'not_verified': ['psycopg2 runtime and real exception translation', 'Real replica/read-only connections', 'PostgreSQL behavior', 'Pool lifecycle',
                     'Concurrent thread isolation', 'SQL hooks', 'Nested transactions',
                     'Production caller acceptance', 'Reference runtime tests'],
    'reproduction': 'THYROX_CONSUMER=<API checkout> ODOO_TOOLS=<verified reference checkout> UV_CACHE_DIR=<cache> uv run --frozen python <probe_cursor_replica_flow.py>',
}
destination = Path(__file__).with_name('cursor-replica-observations.json')
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'cases': CASES, 'negative_controls': report['negative_controls'], 'evidence': str(destination)}, indent=2))
