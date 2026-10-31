"""Compare real metadata flags with pinned reference property bodies.

The reference fixture extracts only initialization and property accessors.
It is not native Odoo execution or qualification of its complete Registry.
"""

import __future__
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import threading

from orm import registry as consumer
from reference_roots import TOOLS_ROOT, tree

REVISION = 'abe4040ec1a45beee90fb694e4eae4453e46b389'
JOB = Path(__file__).resolve().parents[1]


def reference_fixture(source):
    cls = next(n for n in ast.parse(source).body
               if isinstance(n, ast.ClassDef) and n.name == 'Registry')
    initialize = deepcopy(next(n for n in cls.body
                               if isinstance(n, ast.FunctionDef)
                               and n.name == 'init'))
    initialize.name = '__init__'
    initialize.decorator_list = []
    initialize.body = [
        n for n in initialize.body
        if isinstance(n, ast.Assign) and any(
            isinstance(target, ast.Attribute)
            and target.attr == '_invalidation_flags'
            for target in n.targets
        )
    ]
    assert len(initialize.body) == 1
    accessors = [deepcopy(n) for n in cls.body
                 if isinstance(n, ast.FunctionDef)
                 and n.name == 'registry_invalidated']
    assert len(accessors) == 2
    isolated = ast.ClassDef(
        name='PinnedRegistryFlag', bases=[], keywords=[],
        decorator_list=[], body=[initialize, *accessors],
    )
    module = ast.Module(body=[isolated], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {'threading': threading}
    exec(compile(module, 'pinned-registry-flag', 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace['PinnedRegistryFlag']


def trace(create, replace):
    first = create('contract_flag_differential_first')
    first.registry_invalidated = True
    second = create('contract_flag_differential_second')
    rows = [[first.registry_invalidated, second.registry_invalidated]]
    second.registry_invalidated = True
    first.registry_invalidated = False
    rows.append([first.registry_invalidated, second.registry_invalidated])
    replacement = replace('contract_flag_differential_first')
    rows.append([replacement.registry_invalidated,
                 second.registry_invalidated])
    thread_rows = []

    def worker():
        thread_rows.append([replacement.registry_invalidated,
                            second.registry_invalidated])
        replacement.registry_invalidated = True
        thread_rows.append([replacement.registry_invalidated,
                            second.registry_invalidated])

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive() and len(thread_rows) == 2
    return {'same_thread': rows, 'other_thread': thread_rows,
            'parent_after_thread': [replacement.registry_invalidated,
                                    second.registry_invalidated]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--annul-scope', action='store_true')
    args = parser.parse_args()
    actual = subprocess.check_output(
        ['git', '-C', str(TOOLS_ROOT), 'rev-parse', 'HEAD'], text=True
    ).strip()
    assert actual == REVISION
    path = tree('odoo19c') / 'odoo/orm/registry.py'
    source = subprocess.check_output([
        'git', '-C', str(TOOLS_ROOT), 'show',
        f'{REVISION}:{path.relative_to(TOOLS_ROOT).as_posix()}',
    ])
    reference = reference_fixture(source)
    expected = trace(reference, reference)
    original = consumer.Registry.registry_invalidated
    if args.annul_scope:
        preimage = JOB / 'outputs/registry-scope-source-preimage.txt'
        cls = next(n for n in ast.parse(preimage.read_bytes()).body
                   if isinstance(n, ast.ClassDef) and n.name == 'Registry')
        module = ast.Module(body=[n for n in cls.body
                                  if isinstance(n, ast.FunctionDef)
                                  and n.name == 'registry_invalidated'],
                            type_ignores=[])
        namespace = {'_invalidation': consumer._invalidation}
        exec(compile(module, 'annulled-registry-flag', 'exec'), namespace)
        consumer.Registry.registry_invalidated = namespace[
            'registry_invalidated'
        ]
    try:
        observed = trace(consumer.Registry, consumer.Registry.new)
    finally:
        consumer.Registry.registry_invalidated = original
        for name in ('contract_flag_differential_first',
                     'contract_flag_differential_second'):
            consumer.Registry.delete(name)
    report = {
        'reference_revision': actual,
        'reference_sha256': hashlib.sha256(source).hexdigest(),
        'reference_symbol': 'Registry.init/registry_invalidated',
        'reference_trace': expected, 'consumer_trace': observed,
        'equivalent': expected == observed, 'annulled': args.annul_scope,
        'scope': 'Pinned property bodies and real Consumer metadata factory; '
                 'SQL prohibited by caller; no full loader acceptance',
    }
    args.result.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if expected == observed else 1


if __name__ == '__main__':
    raise SystemExit(main())
