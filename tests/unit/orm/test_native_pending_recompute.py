"""Native pending recompute batching; existence IO is explicitly simulated."""

import pytest

import fields
from exceptions import AccessError, MissingError
from orm import fields as field_runtime
from orm import registry
from orm.environments import env, get_context, transaction_scope
from orm.models import BaseModel


class NativePendingProbe(BaseModel):
    _name = 'orm.native.pending.probe'
    value = fields.Char(
        max_length=32, compute='_compute_value', store=True, compute_sudo=False
    )
    calls = []

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_value(self):
        type(self).calls.append(self._ids)
        for record in self:
            record.value = str(record._ids[0])


@pytest.fixture(autouse=True)
def isolated_pending_environment():
    with transaction_scope():
        registry.clear_field_depends()
        NativePendingProbe.calls.clear()
        yield
        registry.clear_field_depends()


def pending(ids=(31, 32), queued=(31, 32)):
    records = NativePendingProbe._from_ids(env(), ids, ids)
    field = NativePendingProbe._meta.get_field('value')
    env().add_to_compute(field, queued)
    return records, field


def test_nonrecursive_pending_records_compute_as_one_batch():
    records, field = pending()
    field.recompute(records)
    assert NativePendingProbe.calls == [(31, 32)]
    assert dict(field._get_cache(env())) == {31: '31', 32: '32'}
    assert not env().transaction.tocompute.get(field)


def test_batch_expands_to_queued_ids_outside_the_initial_record():
    records, field = pending(ids=(31,))
    field.recompute(records)
    assert NativePendingProbe.calls == [(31, 32)]
    assert not env().transaction.tocompute.get(field)


def test_batch_cap_keeps_unselected_work_pending(monkeypatch):
    records, field = pending(ids=(31,), queued=(31, 32, 33))
    monkeypatch.setattr(field_runtime, 'PREFETCH_MAX', 2)
    field.recompute(records)
    assert NativePendingProbe.calls == [(31, 32)]
    assert set(env().transaction.tocompute[field]) == {33}
    assert 33 not in field._get_cache(env())


def test_recursive_computes_pending_singletons_in_input_order(monkeypatch):
    records, field = pending(ids=(31, 32, 33), queued=(31, 33))
    monkeypatch.setattr(field, 'recursive', True)
    field.recompute(records)
    assert NativePendingProbe.calls == [(31,), (33,)]
    assert not env().transaction.tocompute.get(field)


def test_no_pending_work_does_not_invoke_compute():
    records, field = pending(queued=())
    field.recompute(records)
    assert NativePendingProbe.calls == []


def test_missing_batch_retries_existing_and_clears_missing(monkeypatch):
    records, field = pending()
    observed = []
    lookups = []

    def compute(batch):
        observed.append(batch._ids)
        if 32 in batch._ids:
            raise MissingError('missing row')
        for record in batch:
            record.value = 'existing'

    def existing(batch):
        lookups.append(batch._ids)
        return batch.browse((31,))

    monkeypatch.setattr(field, 'compute', compute)
    monkeypatch.setattr(NativePendingProbe, 'exists', existing)
    field.recompute(records)
    assert observed == [(31, 32), (31,)]
    assert lookups == [(31, 32)]
    assert not env().transaction.tocompute.get(field)
    assert dict(field._get_cache(env())) == {31: 'existing'}


def test_persistent_missing_error_has_only_one_retry(monkeypatch):
    records, field = pending()
    observed = []
    error = MissingError('persistent absence')

    def compute(batch):
        observed.append(batch._ids)
        raise error

    monkeypatch.setattr(field, 'compute', compute)
    monkeypatch.setattr(NativePendingProbe, 'exists', lambda batch: batch)
    with pytest.raises(MissingError) as caught:
        field.recompute(records)
    assert caught.value is error
    assert observed == [(31, 32), (31, 32)]
    assert set(env().transaction.tocompute[field]) == {31, 32}


def test_access_error_falls_back_to_singletons_without_hiding_it(monkeypatch):
    records, field = pending()
    observed = []

    def compute(batch):
        observed.append(batch._ids)
        if len(batch) > 1:
            raise AccessError('batch not authorized')
        batch.value = str(batch._ids[0])

    monkeypatch.setattr(field, 'compute', compute)
    field.recompute(records)
    assert observed == [(31, 32), (31,), (32,)]
    assert dict(field._get_cache(env())) == {31: '31', 32: '32'}
    assert not env().transaction.tocompute.get(field)


def test_unrelated_error_propagates_and_restores_pending(monkeypatch):
    records, field = pending()
    observed = []
    error = RuntimeError('not an absence or access error')

    def compute(batch):
        observed.append(batch._ids)
        raise error

    monkeypatch.setattr(field, 'compute', compute)
    with pytest.raises(RuntimeError) as caught:
        field.recompute(records)
    assert caught.value is error
    assert observed == [(31, 32)]
    assert set(env().transaction.tocompute[field]) == {31, 32}
    assert all(not env().is_protected(field, id_) for id_ in (31, 32))


def test_attached_context_is_active_only_during_recompute(monkeypatch):
    records, field = pending()
    records = records.with_context(pending_probe='attached')
    before = dict(get_context())
    observed = []

    def compute(batch):
        observed.append(get_context().get('pending_probe'))
        for record in batch:
            record.value = 'attached'

    monkeypatch.setattr(field, 'compute', compute)
    field.recompute(records)
    assert observed == ['attached']
    assert dict(get_context()) == before


def test_singleton_access_denial_propagates_and_keeps_work(monkeypatch):
    records, field = pending()
    observed = []
    error = AccessError('also denied for singleton')

    def compute(batch):
        observed.append(batch._ids)
        raise error

    monkeypatch.setattr(field, 'compute', compute)
    with pytest.raises(AccessError) as caught:
        field.recompute(records)
    assert caught.value is error
    assert observed == [(31, 32), (31,)]
    assert set(env().transaction.tocompute[field]) == {31, 32}


class NativeMissingGroupProbe(BaseModel):
    _name = 'orm.native.missing.group.probe'
    first = fields.Char(compute='_compute_pair', store=True)
    second = fields.Char(compute='_compute_pair', store=True)

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_pair(self):
        raise MissingError('all group rows disappeared')


def test_all_missing_ids_are_removed_from_each_computed_field(monkeypatch):
    records = NativeMissingGroupProbe._from_ids(env(), (31, 32), (31, 32))
    first = NativeMissingGroupProbe._meta.get_field('first')
    second = NativeMissingGroupProbe._meta.get_field('second')
    assert set(registry.field_computed[first]) == {first, second}
    for field in (first, second):
        env().add_to_compute(field, (31, 32))
    monkeypatch.setattr(
        NativeMissingGroupProbe, 'exists', lambda batch: batch.browse(())
    )
    first.recompute(records)
    for field in (first, second):
        assert not env().transaction.tocompute.get(field)
        assert dict(field._get_cache(env())) == {}
