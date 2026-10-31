"""Contrato de create_categories con identidades y transacciones reales."""
import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModuleCategory
from modules import db as module_db


pytestmark = [pytest.mark.integration, pytest.mark.django_db]
ROOT = 'ContractTree'


def _create(segments):
    with connection.cursor() as cursor:
        return module_db.create_categories(cursor, segments)


def _identity(name, record_id, model='base.IrModuleCategory'):
    return IrModelData.objects.create(
        module='base', name=name, model=model, res_id=record_id,
        noupdate=True,
    )


def test_empty_path_has_no_side_effects():
    before = (IrModuleCategory.objects.count(), IrModelData.objects.count())
    assert _create([]) is None
    assert (IrModuleCategory.objects.count(), IrModelData.objects.count()) == before


def test_nested_path_creates_each_level_and_its_external_identity():
    segments = [ROOT, 'Child', 'Leaf']
    leaf = IrModuleCategory.objects.get(pk=_create(segments))

    assert segments == [ROOT, 'Child', 'Leaf']
    assert leaf.name == 'Leaf'
    assert leaf.parent.name == 'Child'
    assert leaf.parent.parent.name == ROOT
    assert leaf.parent.parent.parent_id is None
    for record, name in [
        (leaf.parent.parent, 'module_category_contracttree'),
        (leaf.parent, 'module_category_contracttree_child'),
        (leaf, 'module_category_contracttree_child_leaf'),
    ]:
        identity = IrModelData.objects.get(module='base', name=name)
        assert (identity.model, identity.res_id, identity.noupdate) == (
            'base.IrModuleCategory', record.pk, True,
        )


def test_unicode_and_native_xmlid_normalization_preserve_visible_name():
    label = 'ContractTree Árbol & Child'
    record_id = _create([label])
    assert IrModuleCategory.objects.get(pk=record_id).name == label
    assert IrModelData.objects.get(
        module='base', name='module_category_contracttree_árbol_and_child',
    ).res_id == record_id


def test_repeated_path_reuses_identity_and_shared_prefix():
    first = _create([ROOT, 'First'])
    counts = (IrModuleCategory.objects.count(), IrModelData.objects.count())
    assert _create([ROOT, 'First']) == first
    assert (IrModuleCategory.objects.count(), IrModelData.objects.count()) == counts

    second = _create([ROOT, 'Second'])
    first = IrModuleCategory.objects.get(pk=first)
    second = IrModuleCategory.objects.get(pk=second)
    assert first.pk != second.pk
    assert first.parent_id == second.parent_id
    assert IrModuleCategory.objects.count() == counts[0] + 1


def test_renamed_visible_category_keeps_its_external_identity():
    record_id = _create([ROOT])
    IrModuleCategory.objects.filter(pk=record_id).update(name='Renamed display')

    assert _create([ROOT]) == record_id
    assert IrModuleCategory.objects.get(pk=record_id).name == 'Renamed display'


def test_caller_rollback_preserves_ownership_of_the_transaction():
    with pytest.raises(RuntimeError, match='caller rollback'):
        with transaction.atomic():
            _create([ROOT, 'Child'])
            raise RuntimeError('caller rollback')

    assert not IrModuleCategory.objects.filter(name=ROOT).exists()
    assert not IrModelData.objects.filter(name__startswith='module_category_contracttree').exists()


def test_wrong_model_identity_is_not_overwritten_and_new_parents_roll_back():
    identity = _identity('module_category_contracttree_child', 123, 'base.IrModule')

    with pytest.raises(ValidationError):
        _create([ROOT, 'Child'])

    identity.refresh_from_db()
    assert (identity.model, identity.res_id) == ('base.IrModule', 123)
    assert not IrModuleCategory.objects.filter(name=ROOT).exists()


def test_missing_target_identity_is_not_silently_repaired():
    identity = _identity('module_category_contracttree', 2147483647)

    with pytest.raises(ValidationError):
        _create([ROOT])

    identity.refresh_from_db()
    assert identity.res_id == 2147483647
    assert not IrModuleCategory.objects.filter(name=ROOT).exists()


def test_incompatible_parent_identity_does_not_merge_distinct_trees():
    other = IrModuleCategory.objects.create(name='Other category')
    child = IrModuleCategory.objects.create(name='Child', parent=other)
    _identity('module_category_contracttree_child', child.pk)

    with pytest.raises(ValidationError):
        _create([ROOT, 'Child'])

    child.refresh_from_db()
    assert child.parent_id == other.pk
    assert not IrModuleCategory.objects.filter(name=ROOT).exists()


def test_external_identity_length_limit_never_truncates_a_path():
    with pytest.raises(ValidationError, match='255'):
        _create([ROOT + 'Ω' * 255])

    assert not IrModuleCategory.objects.filter(name__startswith=ROOT).exists()
