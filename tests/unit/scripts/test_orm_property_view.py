"""Logical properties retain accessor and reference identities separately."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB = ROOT / 'scripts/evidence/orm-demo-continuation-20261023T144219'
SPEC = importlib.util.spec_from_file_location(
    'orm_property_view', JOB / 'probes/reconcile_structural_view.py'
)
VIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIEW)
INVENTORY = json.loads(
    (JOB / 'outputs' / 'continuation-20261030-reference-inventory.json')
    .read_text()
)
REVISION = 'abe4040ec1a45beee90fb694e4eae4453e46b389'


def accessors(file_name, owner_name, property_name):
    entry = next(f for f in INVENTORY['files'] if f['name'] == file_name)
    owner = next(c for c in entry['classes'] if c['name'] == owner_name)
    rows = []
    for record in owner['methods']:
        if record['name'] != property_name:
            continue
        qualified = owner_name + '.' + property_name
        path = 'odoo/orm/' + file_name
        rows.append({
            'identity': [REVISION, path, qualified,
                         'property_accessor', record['lineno']],
            'reference_revision': REVISION,
            'reference_path': path,
            'qualified_symbol': qualified,
            'declaring_owner': owner_name,
            'declaration_kind': 'property_accessor',
            'decorators': record['decorators'],
        })
    assert rows
    return rows


def test_registry_getter_and_setter_are_one_logical_property():
    rows = accessors('registry.py', 'Registry', 'registry_invalidated')
    result = VIEW.logical_property_groups(rows)
    assert len(rows) == 2 and len(result) == 1
    assert {a['role'] for a in result[0]['accessors']} == {'getter', 'setter'}
    assert result[0]['equivalence'] == 'not_verified'


def test_homonymous_properties_in_different_classes_stay_distinct():
    rows = accessors('fields.py', 'Field', 'column_type')
    rows += accessors('fields_binary.py', 'Binary', 'column_type')
    assert len(VIEW.logical_property_groups(rows)) == 2


def test_different_reference_revisions_do_not_merge():
    rows = accessors('registry.py', 'Registry', 'registry_invalidated')[:1]
    other = deepcopy(rows[0])
    other['reference_revision'] = 'other-reference'
    other['identity'][0] = 'other-reference'
    assert len(VIEW.logical_property_groups(rows + [other])) == 2


def test_duplicate_accessor_identity_is_rejected():
    rows = accessors('registry.py', 'Registry', 'registry_invalidated')
    with pytest.raises(ValueError, match='duplicate'):
        VIEW.logical_property_groups(rows + [rows[0]])


@pytest.mark.parametrize(
    'field', ['reference_revision', 'reference_path', 'qualified_symbol',
              'declaring_owner'],
)
def test_inconsistent_accessor_provenance_is_rejected(field):
    row = accessors('registry.py', 'Registry', 'registry_invalidated')[0]
    row[field] = 'different-reference'
    with pytest.raises(ValueError, match='identity'):
        VIEW.logical_property_groups([row])


@pytest.mark.parametrize(
    'decorators', [[], ['unknown_descriptor'], ['property', 'flag.setter']],
)
def test_unverified_or_ambiguous_accessor_role_is_rejected(decorators):
    row = accessors('registry.py', 'Registry', 'registry_invalidated')[0]
    row['decorators'] = decorators
    with pytest.raises(ValueError, match='role'):
        VIEW.logical_property_groups([row])


def test_static_attributes_preserve_owners_and_declaration_limits(tmp_path):
    source = tmp_path / 'source.py'
    source.write_text(
        'LIMIT = 1\n'
        'class First:\n'
        '    value = 2\n'
        '    annotated: int = 3\n'
        '    def initialize(self):\n'
        '        self.dynamic = 4\n'
        '        class Local:\n'
        '            value = 5\n'
        'class Second:\n'
        '    value = 6\n'
        'if True:\n'
        '    CONDITIONAL = 7\n'
    )
    result = VIEW.static_attribute_rows(source, REVISION, 'source.py')
    assert {row['qualified_symbol'] for row in result['rows']} == {
        'LIMIT', 'First.value', 'Second.value',
    }
    assert all(row['equivalence'] == 'not_verified'
               for row in result['rows'])
    assert result['applicable_contract_denominator'] is None
    assert 'annotated assignments' in result['limitations']
    assert 'inherited and dynamic members' in result['limitations']


@pytest.mark.parametrize('source_bytes', [b'class Broken:', b'\xff'])
def test_invalid_attribute_source_cannot_be_an_empty_population(
    tmp_path, source_bytes
):
    source = tmp_path / 'source.py'
    source.write_bytes(source_bytes)
    with pytest.raises(ValueError, match='source'):
        VIEW.static_attribute_rows(source, REVISION, 'source.py')


def test_redeclared_class_attributes_retain_both_occurrences(tmp_path):
    source = tmp_path / 'source.py'
    source.write_text('class Same:\n    value = 1\n'
                      'class Same:\n    value = 2\n')
    rows = VIEW.static_attribute_rows(source, REVISION, 'source.py')['rows']
    assert len(rows) == 2
    assert rows[0]['identity'] != rows[1]['identity']


@pytest.mark.parametrize('fault', [None, 'revision', 'source_hash'])
def test_attribute_snapshot_reuses_only_bound_sources(
    tmp_path, monkeypatch, fault
):
    reference = tmp_path / 'reference'
    consumer = tmp_path / 'consumer'
    files = []
    for name in ('registry.py', 'fields.py'):
        relative = 'odoo/orm/' + name
        source = reference / relative
        target = consumer / 'src/orm' / name
        source.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('class Sample:\n    enabled = True\n')
        target.write_text('class Sample:\n    enabled = False\n')
        files.append({
            'reference_path': relative,
            'reference_sha256': hashlib.sha256(
                source.read_bytes()
            ).hexdigest(),
            'consumer_path': 'src/orm/' + name,
        })
    snapshot = tmp_path / 'capture.json'
    captured = {'source_revision': REVISION, 'files': files}
    if fault == 'revision':
        captured['source_revision'] = 'different-reference'
    elif fault == 'source_hash':
        files[0]['reference_sha256'] = 'wrong'
    snapshot.write_text(json.dumps(captured))
    monkeypatch.setattr(VIEW, 'TOOLS_ROOT', reference)
    monkeypatch.setattr(VIEW, 'ROOT', consumer)
    monkeypatch.setattr(VIEW, 'tree', lambda alias: reference)
    if fault:
        with pytest.raises(ValueError, match='snapshot|revision|bytes'):
            VIEW.attribute_snapshot(snapshot)
        return
    result = VIEW.attribute_snapshot(snapshot)
    assert result['observed_static_assignments'] == 2
    for file in result['files']:
        row = file['rows'][0]
        assert len(row['consumer_candidates']) == 1
        assert row['consumer_candidates'][0]['equivalence'] == 'not_verified'
        assert file['consumer_sha256'] != file['source_sha256']
