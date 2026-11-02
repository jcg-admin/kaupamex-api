"""Reentrant callbacks may consume work in a later row of the same batch.

These controls execute the Django-backed compute and queue machinery without
SQL; native recordset batching keeps its separate contract.
"""

from django.db import models
import pytest

import fields
from exceptions import AccessError
from orm import registry
from orm.environments import env, transaction_scope


class ReentryComputeProbe(models.Model):
    _name = 'orm.recompute.reentry.probe'
    _description = 'Pending recompute reentry contract'
    source = fields.Integer(default=0)
    value = fields.Integer(
        compute='_compute_value', store=True, compute_sudo=False, null=True
    )
    calls = []

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_value(self):
        type(self).calls.append(self.pk)
        self.value = self.source * 2


@pytest.fixture
def reentry_fixture():
    with transaction_scope():
        registry.clear_field_depends()
        ReentryComputeProbe.calls.clear()
        first = ReentryComputeProbe(pk=31, source=3)
        second = ReentryComputeProbe(pk=32, source=5)
        field = ReentryComputeProbe._meta.get_field('value')
        env().add_to_compute(field, [31, 32])
        yield first, second, field
        registry.clear_field_depends()


@pytest.mark.parametrize('recursive', [False, True])
def test_reentry_respects_recursive_and_legacy_callback_contracts(
    reentry_fixture, monkeypatch, recursive
):
    first, second, field = reentry_fixture
    original = ReentryComputeProbe._compute_value

    def compute(record):
        if record.pk == 31:
            field.compute_value(second)
        original(record)

    monkeypatch.setattr(field, 'recursive', recursive)
    monkeypatch.setattr(ReentryComputeProbe, '_compute_value', compute)
    field.recompute([first, second])
    expected = [32, 31] if recursive else [32, 31, 32]
    assert ReentryComputeProbe.calls == expected
    assert dict(field._get_cache(env())) == {31: 6, 32: 10}
    assert not env().transaction.tocompute.get(field)


def test_new_work_outside_input_remains_queued(reentry_fixture, monkeypatch):
    first, second, field = reentry_fixture
    original = ReentryComputeProbe._compute_value

    def compute(record):
        if record.pk == 31:
            env().add_to_compute(field, [33])
        original(record)

    monkeypatch.setattr(ReentryComputeProbe, '_compute_value', compute)
    field.recompute([first, second])
    assert ReentryComputeProbe.calls == [31, 32]
    assert set(env().transaction.tocompute[field]) == {33}
    assert 33 not in field._get_cache(env())


def test_nested_denial_restores_both_pending_rows(
    reentry_fixture, monkeypatch
):
    first, second, field = reentry_fixture
    error = AccessError('nested compute denied')

    def compute(record):
        if record.pk == 32:
            raise error
        field.compute_value(second)

    monkeypatch.setattr(ReentryComputeProbe, '_compute_value', compute)
    with pytest.raises(AccessError) as caught:
        field.recompute([first, second])
    assert caught.value is error
    assert set(env().transaction.tocompute[field]) == {31, 32}
    assert all(not env().is_protected(field, id_) for id_ in (31, 32))
