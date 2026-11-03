"""Derive a partial ORM view from qualified instruments, not a new authority.

The reference inventory defines the population. The existing body resolver
supplies candidate mappings only. Neither presence nor these mappings proves
applicability, functional equivalence, integration or acceptance.
"""

from collections import Counter
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from check_model_class_attributes import class_underscore_attrs
from counterpart_body import (
    Declaration, declarations_of, pair_declarations, parse_file,
)
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


def static_attribute_rows(path, revision, relative, *,
                          include_annotations=False):
    """Project direct assignments from the existing declaration extractor.

    This is an observation population, separate from the 954 declarations.
    It neither resolves inherited members nor evaluates assigned values.
    """
    path = Path(path)
    try:
        source = path.read_bytes()
        source.decode('utf-8')
    except (OSError, UnicodeError) as error:
        raise ValueError('unreadable attribute source') from error
    parsed = parse_file(path)
    if parsed is None:
        raise ValueError('invalid attribute source')
    declarations = declarations_of(path, tree=parsed)
    owners = [
        declaration
        for declaration in declarations
        if declaration.kind == 'class' and declaration.node in parsed.body
    ]
    buckets = {}
    for owner in owners:
        classified = class_underscore_attrs(owner.node)
        for bucket, attributes in zip(('orm', 'table', 'other'), classified):
            for name, line in attributes.items():
                buckets[(owner.name, name, line)] = bucket
    annotation_only = []
    if include_annotations:
        bodies = [('', parsed.body)] + [
            (owner.name, owner.node.body) for owner in owners
        ]
        # The existing declaration extractor omits AnnAssign. Supplement this
        # measured gap using its parsed scopes, not another parser or census.
        for owner, body in bodies:
            for statement in body:
                if not (isinstance(statement, ast.AnnAssign)
                        and isinstance(statement.target, ast.Name)):
                    continue
                name = statement.target.id
                if statement.value is None:
                    qualified = f'{owner}.{name}' if owner else name
                    annotation_only.append({
                        'identity': [revision, relative, qualified,
                                     'annotation_only', statement.lineno],
                        'qualified_symbol': qualified,
                        'annotation_expression': ast.unparse(
                            statement.annotation
                        ),
                        'runtime_binding': 'not_established_by_annotation',
                        'applicability': 'not_verified',
                    })
                else:
                    declarations.append(Declaration(
                        name, owner, statement.lineno, statement, (), 'assign'
                    ))
    rows = []
    for declaration in declarations:
        if declaration.kind != 'assign':
            continue
        direct = (
            any(declaration.node in owner.node.body
                for owner in owners if owner.name == declaration.owner)
            if declaration.owner else declaration.node in parsed.body
        )
        if not direct:
            continue
        qualified = (f'{declaration.owner}.{declaration.name}'
                     if declaration.owner else declaration.name)
        kind = ('annotated_value_binding'
                if isinstance(declaration.node, ast.AnnAssign)
                else 'static_assignment')
        rows.append({
            'identity': [revision, relative, qualified,
                         kind, declaration.lineno],
            'qualified_symbol': qualified,
            'declaring_owner': declaration.owner,
            'value_expression_kind': type(declaration.node.value).__name__,
            'model_checker_bucket': buckets.get(
                (declaration.owner, declaration.name, declaration.lineno),
                'not_classified',
            ),
            'applicability': 'not_verified',
            'equivalence': 'not_verified',
            'integration': 'not_verified',
            'acceptance': 'not_verified',
        })
    identities = [tuple(row['identity']) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError('Duplicate attribute declaration identity')
    return {
        'reference_revision': revision,
        'reference_path': relative,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'interface': 'counterpart_body.declarations_of/parse_file',
        'rows': rows,
        'annotation_only': annotation_only,
        'annotations_included': include_annotations,
        'classification_interface': (
            'check_model_class_attributes.class_underscore_attrs; '
            'detector buckets do not establish contractual applicability'
        ),
        'applicable_contract_denominator': None,
        'limitations': ([] if include_annotations else [
            'annotated assignments',
        ]) + [
            'conditional assignments', 'destructuring assignment targets',
            'inherited and dynamic members',
            'runtime values and descriptor behavior',
            'only direct simple-name module and module-level class bindings',
            'contractual roles of constants/type aliases not established',
        ],
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


def attribute_snapshot(snapshot, *, all_captured=False,
                       include_annotations=False):
    """Extend captured files without rerunning the reference inventory."""
    captured = json.loads(snapshot.read_text())
    if captured['source_revision'] != REVISION:
        raise ValueError('Reconcile changed snapshot reference')
    names = ['registry.py', 'fields.py']
    if all_captured:
        names = [Path(entry['consumer_path']).name
                 for entry in captured['files']]
        if not names or len(names) != len(set(names)):
            raise ValueError('Missing or duplicate captured sources')
    files = []
    for name in names:
        entries = [entry for entry in captured['files']
                   if entry['consumer_path'] == f'src/orm/{name}']
        if len(entries) != 1:
            raise ValueError('Missing or ambiguous captured source')
        entry = entries[0]
        source = tree('odoo19c') / 'odoo/orm' / name
        relative = source.relative_to(TOOLS_ROOT).as_posix()
        if relative != entry['reference_path']:
            raise ValueError('Captured source path disagrees with resolver')
        view = static_attribute_rows(
            source, REVISION, relative,
            include_annotations=include_annotations,
        )
        if view['source_sha256'] != entry['reference_sha256']:
            raise ValueError('Captured source revision or bytes changed')
        target = ROOT / entry['consumer_path']
        before = target.read_bytes() if target.is_file() else None
        matches = {}
        if before is not None:
            candidates = static_attribute_rows(
                target, 'working-source', entry['consumer_path'],
                include_annotations=include_annotations,
            )
            for candidate in candidates['rows']:
                matches.setdefault(
                    candidate['qualified_symbol'], []
                ).append({
                    'path': entry['consumer_path'],
                    'symbol': candidate['qualified_symbol'],
                    'owner': candidate['declaring_owner'],
                    'line': candidate['identity'][-1],
                    'route': ('same qualified static assignment; '
                              'candidate only'),
                    'equivalence': 'not_verified',
                })
        after = target.read_bytes() if target.is_file() else None
        if before != after:
            raise ValueError('Consumer source changed during observation')
        for row in view['rows']:
            row['consumer_candidates'] = matches.get(
                row['qualified_symbol'], []
            )
        view['consumer_path'] = entry['consumer_path']
        view['consumer_sha256'] = (
            hashlib.sha256(before).hexdigest() if before is not None else None
        )
        files.append(view)
    return {
        'source_revision': REVISION,
        'snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        'consumer_revision': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], text=True
        ).strip(),
        'consumer_revision_scope': 'HEAD plus observed working source hashes',
        'files': files,
        'observed_static_assignments': sum(
            row['identity'][3] == 'static_assignment'
            for file in files for row in file['rows']
        ),
        'observed_annotated_bindings': sum(
            row['identity'][3] == 'annotated_value_binding'
            for file in files for row in file['rows']
        ),
        'observed_value_bindings_total': sum(len(f['rows']) for f in files),
        'annotation_only_declarations': sum(
            len(file['annotation_only']) for file in files
        ),
        'scope': (
            ('All captured files' if all_captured else 'Two captured files')
            + '; direct simple-name bindings, no repeated inventory'
        ),
        'annotations_included': include_annotations,
        'applicable_contract_denominator': None,
        'functional_coverage': None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', type=Path,
        default=JOB / 'outputs/continuation-20261030-structural-view.json',
    )
    parser.add_argument('--attribute-snapshot', type=Path)
    parser.add_argument('--all-captured-attributes', action='store_true')
    parser.add_argument('--include-annotations', action='store_true')
    arguments = parser.parse_args()
    attribute_options = (
        arguments.all_captured_attributes or arguments.include_annotations
    )
    if attribute_options and arguments.attribute_snapshot is None:
        parser.error('Attribute options require --attribute-snapshot')
    revision = subprocess.check_output(
        ['git', '-C', str(TOOLS_ROOT), 'rev-parse', 'HEAD'], text=True
    ).strip()
    if revision != REVISION:
        raise ValueError('Reconcile changed reference before measuring')
    if arguments.attribute_snapshot is not None:
        result = attribute_snapshot(
            arguments.attribute_snapshot,
            all_captured=arguments.all_captured_attributes,
            include_annotations=arguments.include_annotations,
        )
        arguments.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({
            'output': str(arguments.output),
            'files': len(result['files']),
            'observed_static_assignments': result[
                'observed_static_assignments'
            ],
            'applicable_contract_denominator': None,
        }))
        return
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
