"""Stored native compute values must survive the Django read-back bridge."""

from django.db import models
import pytest

import fields
from orm import registry
from orm.environments import env, transaction_scope
from orm.models import BaseModel


class NativeStoredProbe(BaseModel):
    _name = 'orm.native.stored.compute.probe'
    computed = fields.Char(
        max_length=32, compute='_compute_value', store=True, compute_sudo=False
    )

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_value(self):
        for record in self:
            record.computed = str(record._ids[0])


class LegacyStoredRow(models.Model):
    computed = fields.Char(
        max_length=32, compute='_compute_value', store=True, compute_sudo=False
    )

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_value(self):
        self.computed = str(self.pk)


@pytest.fixture(autouse=True)
def isolated_stored_compute_environment():
    with transaction_scope():
        registry.clear_field_depends()
        yield
        registry.clear_field_depends()


@pytest.mark.parametrize('ids', [(31, 32), (31,), ()])
def test_native_stored_compute_preserves_each_cache_value(ids):
    records = NativeStoredProbe._from_ids(env(), ids, ids)
    field = NativeStoredProbe._meta.get_field('computed')
    env().add_to_compute(field, ids)
    field.compute_value(records)
    assert dict(field._get_cache(env())) == {id_: str(id_) for id_ in ids}
    assert not env().transaction.tocompute.get(field)
    assert env().transaction.field_dirty.get(field, set()) == set(ids)


def test_native_stored_failure_restores_all_pending_ids():
    ids = (31, 32)
    records = NativeStoredProbe._from_ids(env(), ids, ids)
    field = NativeStoredProbe._meta.get_field('computed')
    env().add_to_compute(field, ids)
    original = field.compute
    error = RuntimeError('stored compute failure')

    def fail(batch):
        for record in batch:
            record.computed = 'partial'
            raise error

    try:
        field.compute = fail
        with pytest.raises(RuntimeError) as caught:
            field.compute_value(records)
    finally:
        field.compute = original
    assert caught.value is error
    assert set(env().transaction.tocompute[field]) == set(ids)
    assert all(not env().is_protected(field, id_) for id_ in ids)


def test_legacy_stored_readback_retains_distinct_row_values():
    rows = [LegacyStoredRow(pk=31), LegacyStoredRow(pk=32)]
    field = LegacyStoredRow._meta.get_field('computed')
    env().add_to_compute(field, (31, 32))
    field.compute_value(rows)
    assert dict(field._get_cache(env())) == {31: '31', 32: '32'}
    assert not env().transaction.tocompute.get(field)
