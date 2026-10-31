"""Logical properties retain accessor and reference identities separately."""

from copy import deepcopy
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
