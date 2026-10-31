"""Derive a partial ORM view from qualified instruments, not a new authority.

The reference inventory defines the population. The existing body resolver
supplies candidate mappings only. Neither presence nor these mappings proves
applicability, functional equivalence, integration or acceptance.
"""

from collections import Counter
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from counterpart_body import pair_declarations
from reference_roots import TOOLS_ROOT, tree

REVISION = 'abe4040ec1a45beee90fb694e4eae4453e46b389'
JOB = Path(__file__).resolve().parents[1]
ROOT = JOB.parents[2]
INSTRUMENT = (
    ROOT / 'scripts/workbench/'
    'odoo-orm-reference-inventory-20260910T181517/'
    'inventory_reference_orm.py'
)
PROPERTY_DECORATORS = {
    'property', 'cached_property', 'functools.cached_property',
    'classproperty',
}


def logical_property_groups(rows):
    """Group recognized accessors without asserting runtime equivalence."""
    groups = {}
    seen = set()
    for row in rows:
        if row['declaration_kind'] != 'property_accessor':
            continue
        identity = tuple(row['identity'])
        prefix = (row['reference_revision'], row['reference_path'],
                  row['qualified_symbol'], 'property_accessor')
        owner = row['declaring_owner']
        if (
            len(identity) != 5 or identity[:4] != prefix
            or type(identity[-1]) is not int or identity[-1] <= 0
            or not all(isinstance(value, str) and value
                       for value in (*prefix[:3], owner))
            or row['qualified_symbol'].rsplit('.', 1)[0] != owner
        ):
            raise ValueError('inconsistent property accessor identity')
        if identity in seen:
            raise ValueError('duplicate property accessor identity')
        seen.add(identity)
        decorators = set(row['decorators'])
        roles = set()
        if decorators & PROPERTY_DECORATORS:
            roles.add('getter')
        if any(name.endswith('.setter') for name in decorators):
            roles.add('setter')
        if any(name.endswith('.deleter') for name in decorators):
            roles.add('deleter')
        if len(roles) != 1:
            raise ValueError('unverified or ambiguous property accessor role')
        key = (row['reference_revision'], row['reference_path'],
               row['declaring_owner'], row['qualified_symbol'])
        group = groups.setdefault(key, {
            'identity': list(key), 'accessors': [],
            'applicability': 'not_verified', 'equivalence': 'not_verified',
            'integration': 'not_verified', 'acceptance': 'not_verified',
        })
        group['accessors'].append({
            'declaration_identity': list(identity),
            'role': roles.pop(), 'decorators': sorted(decorators),
        })
    return [groups[key] for key in sorted(groups)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', type=Path,
        default=JOB / 'outputs/continuation-20261030-structural-view.json',
    )
    arguments = parser.parse_args()
    revision = subprocess.check_output(
        ['git', '-C', str(TOOLS_ROOT), 'rev-parse', 'HEAD'], text=True
    ).strip()
    if revision != REVISION:
        raise ValueError('Reconcile changed reference before measuring')
    spec = importlib.util.spec_from_file_location('reference_view', INSTRUMENT)
    instrument = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = instrument
    spec.loader.exec_module(instrument)
    reference = tree('odoo19c') / 'odoo/orm'
    inventory = instrument.inventory(reference)
    if not inventory['root_exists'] or not inventory['files']:
        raise ValueError('Reference missing: no zero population is published')
    rows = []
    file_rows = []
    for entry in inventory['files']:
        source = reference / entry['name']
        target = ROOT / 'src/orm' / entry['name']
        relative = source.relative_to(TOOLS_ROOT).as_posix()
        matches = {}
        if target.is_file():
            for pair in pair_declarations(target, source):
                matches.setdefault(pair.theirs.lineno, []).append({
                    'path': target.relative_to(ROOT).as_posix(),
                    'symbol': pair.ours.name,
                    'line': pair.ours.lineno,
                    'route': pair.route,
                    'equivalence': 'not_verified',
                })
        file_rows.append({
            'reference_path': relative,
            'reference_sha256': hashlib.sha256(
                source.read_bytes()
            ).hexdigest(),
            'consumer_path': target.relative_to(ROOT).as_posix(),
            'consumer_exists': target.is_file(),
            'consumer_sha256': (
                hashlib.sha256(target.read_bytes()).hexdigest()
                if target.is_file() else None
            ),
            'completeness': 'not_verified',
        })
        declarations = [(record, '', 'function')
                        for record in entry['functions']]
        for owner in entry['classes']:
            declarations.append((owner, '', 'class'))
            for record in owner['methods']:
                decorators = set(record['decorators'])
                is_property = bool(decorators & PROPERTY_DECORATORS) or any(
                    name.endswith(('.setter', '.deleter'))
                    for name in decorators
                )
                kind = 'property_accessor' if is_property else 'method'
                declarations.append((record, owner['name'], kind))
        for record, owner, kind in declarations:
            qualified = (
                f'{owner}.{record["name"]}' if owner else record['name']
            )
            rows.append({
                'identity': [REVISION, relative, qualified,
                             kind, record['lineno']],
                'reference_revision': REVISION,
                'reference_path': relative,
                'qualified_symbol': qualified,
                'declaration_kind': kind,
                'decorators': record.get('decorators', []),
                'declaring_owner': owner,
                'applicability': 'not_verified',
                'consumer_candidates': matches.get(record['lineno'], []),
                'mapping_evidence': 'counterpart_body.pair_declarations',
                'equivalence': 'not_verified',
                'integration': 'not_verified',
                'acceptance': 'not_verified',
            })
    identities = [tuple(row['identity']) for row in rows]
    assert len(identities) == len(set(identities))
    assert len(rows) == inventory['totals']['symbols']
    properties = logical_property_groups(rows)
    result = {
        'source_revision': revision,
        'consumer_revision': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], text=True
        ).strip(),
        'consumer_revision_scope': (
            'HEAD plus per-file working-tree hashes; no acceptance inferred'
        ),
        'interfaces': ['inventory_reference_orm.inventory',
                       'counterpart_body.pair_declarations'],
        'instrument_sha256': hashlib.sha256(
            INSTRUMENT.read_bytes()
        ).hexdigest(),
        'scope': 'Existing odoo/orm inventory only; not the full corpus',
        'classification': 'Property accessor declarations excluded from '
                          'method count; overload occurrences keep line ID',
        'observed_counts': dict(Counter(
            row['declaration_kind'] for row in rows
        )),
        'files': file_rows,
        'population': rows,
        'logical_properties': properties,
        'logical_property_count': len(properties),
        'applicable_contract_denominator': None,
        'structurally_satisfied': None,
        'functional_coverage': None,
        'limitations': [
            'No class or cross-file correspondence inferred from names',
            'Conditional declarations and closures retain inventory limits',
            'Instance/class attributes not fully covered by this population',
            'Descriptors assigned outside recognized decorators not verified',
            'test_orm and other families retain separate populations',
        ],
    }
    output = arguments.output
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({
        'output': str(output), 'files': len(file_rows),
        'observed_counts': result['observed_counts'],
        'logical_property_count': len(properties),
        'identities_unique': True, 'contract_denominator': None,
    }))


if __name__ == '__main__':
    main()
