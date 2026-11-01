"""Direct native compute dispatch preserves batches, unlike queued recompute.

TASK-GEN-0558 remains open: these controls do not accept pending selection,
recursive ordering, missing-record retries or database prefetch behavior.
"""

from types import SimpleNamespace

from django.db import models
import pytest

import fields
from orm import registry
from orm.environments import env, transaction_scope
from orm.models import BaseModel


class NativeBatchProbe(BaseModel):
    _name = 'orm.native.compute.batch.probe'
    computed = fields.Char(compute='_compute_value', compute_sudo=False)
    observed = None

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_value(self):
        self.observed.append(self)


class LegacyBatchRow(models.Model):
    computed = fields.Char(compute='_compute_value', compute_sudo=False)
    observed = None

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_value(self):
        self.observed.append(self)


@pytest.fixture(autouse=True)
def isolated_compute_environment():
    with transaction_scope():
        registry.clear_field_depends()
        yield
        registry.clear_field_depends()


@pytest.mark.parametrize('ids', [(31, 32), (31,), ()])
def test_native_named_callback_receives_the_original_batch(ids):
    prefetch = (31, 32, 33)
    records = NativeBatchProbe._from_ids(env(), ids, prefetch)
    observed = []
    records.observed = observed
    field = NativeBatchProbe._meta.get_field('computed')
    field.compute_value(records)
    assert len(observed) == 1
    assert observed[0] is records
    assert observed[0]._ids == ids
    assert observed[0]._prefetch_ids is prefetch


def test_native_callable_callback_receives_the_original_batch():
    records = NativeBatchProbe._from_ids(env(), (31, 32), (31, 32, 33))
    observed = []
    field = NativeBatchProbe._meta.get_field('computed')
    original = field.compute
    try:
        field.compute = observed.append
        field.compute_value(records)
    finally:
        field.compute = original
    assert len(observed) == 1
    assert observed[0] is records


def test_legacy_django_rows_keep_per_row_callbacks():
    observed = []
    rows = [LegacyBatchRow(pk=31), LegacyBatchRow(pk=32)]
    for row in rows:
        row.observed = observed
    field = LegacyBatchRow._meta.get_field('computed')
    field.compute_value(rows)
    assert len(observed) == 2
    assert all(actual is expected for actual, expected in zip(observed, rows))


def test_native_callback_exception_is_not_hidden():
    records = NativeBatchProbe._from_ids(env(), (31, 32), (31, 32))
    field = NativeBatchProbe._meta.get_field('computed')
    original = field.compute
    error = RuntimeError('native batch failure')
    callback = SimpleNamespace()
    callback.calls = []

    def fail(batch):
        callback.calls.append(batch)
        raise error

    try:
        field.compute = fail
        with pytest.raises(RuntimeError) as caught:
            field.compute_value(records)
    finally:
        field.compute = original
    assert caught.value is error
    assert len(callback.calls) == 1
    assert callback.calls[0] is records
