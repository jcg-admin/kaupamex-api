"""Pending physical rows survive public-manager visibility predicates.

Query transport is mocked explicitly. These controls do not qualify database
routing, row authorization or a complete native Odoo runtime.
"""

from unittest.mock import Mock

from django.db import models
import pytest

import fields
from exceptions import AccessError
from orm import registry
from orm.environments import env, transaction_scope
from orm.identifiers import NewId
from orm.models import _recompute_field


class VisibleRecomputeRows(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(visible=True)


class RecomputeVisibilityProbe(models.Model):
    _name = 'orm.recompute.visibility.probe'
    source = fields.Integer(default=0)
    visible = models.BooleanField(default=True)
    value = fields.Integer(
        compute='_compute_pair', store=True, null=True, compute_sudo=False
    )
    sibling = fields.Integer(
        compute='_compute_pair', store=True, null=True, compute_sudo=False
    )
    unrelated = fields.Integer(
        compute='_compute_other', store=True, null=True
    )
    objects = VisibleRecomputeRows()
    physical_rows = models.Manager()
    calls = []

    class Meta:
        app_label = 'contenttypes'
        managed = False
        base_manager_name = 'physical_rows'
        default_manager_name = 'objects'

    def _compute_pair(self):
        type(self).calls.append(self.pk)
        self.value = self.source * 2
        self.sibling = self.source * 3

    def _compute_other(self):
        self.unrelated = self.source


@pytest.fixture
def recompute_fixture(monkeypatch):
    with transaction_scope():
        registry.clear_field_depends()
        RecomputeVisibilityProbe.calls.clear()
        first = RecomputeVisibilityProbe(pk=31, source=7, visible=True)
        second = RecomputeVisibilityProbe(pk=32, source=11, visible=False)
        field = RecomputeVisibilityProbe._meta.get_field('value')
        sibling = RecomputeVisibilityProbe._meta.get_field('sibling')
        unrelated = RecomputeVisibilityProbe._meta.get_field('unrelated')
        public = Mock(return_value=[first])
        physical = Mock(return_value=[first, second])
        monkeypatch.setattr(RecomputeVisibilityProbe.objects, 'filter', public)
        monkeypatch.setattr(
            RecomputeVisibilityProbe._base_manager, 'filter', physical
        )
        for computed in (field, sibling):
            env().add_to_compute(computed, [31, 32, 99])
        env().add_to_compute(unrelated, [99])
        yield first, second, field, sibling, unrelated, public, physical
        registry.clear_field_depends()


def test_hidden_existing_pending_row_is_computed(recompute_fixture):
    first, second, field, sibling, unrelated, public, physical = (
        recompute_fixture
    )
    _recompute_field(RecomputeVisibilityProbe, field)
    assert RecomputeVisibilityProbe.calls == [31, 32]
    assert dict(field._get_cache(env())) == {31: 14, 32: 22}
    assert dict(sibling._get_cache(env())) == {31: 21, 32: 33}
    assert not env().transaction.tocompute.get(field)
    assert not env().transaction.tocompute.get(sibling)
    assert set(env().transaction.tocompute[unrelated]) == {99}
    public.assert_not_called()
    physical.assert_called_once_with(pk__in=[31, 32, 99])


def test_requested_subset_preserves_other_pending_rows(recompute_fixture):
    first, second, field, sibling, _, _, physical = recompute_fixture
    physical.return_value = [first]
    _recompute_field(RecomputeVisibilityProbe, field, [31, 99, 777])
    assert RecomputeVisibilityProbe.calls == [31]
    assert set(env().transaction.tocompute[field]) == {32}
    assert set(env().transaction.tocompute[sibling]) == {32}
    physical.assert_called_once_with(pk__in=[31, 99])


def test_only_physical_absence_clears_computed_group(recompute_fixture):
    _, _, field, sibling, unrelated, public, physical = recompute_fixture
    public.return_value = []
    physical.return_value = []
    _recompute_field(RecomputeVisibilityProbe, field)
    assert RecomputeVisibilityProbe.calls == []
    assert not env().transaction.tocompute.get(field)
    assert not env().transaction.tocompute.get(sibling)
    assert set(env().transaction.tocompute[unrelated]) == {99}


def test_physical_lookup_failure_preserves_pending(recompute_fixture):
    _, _, field, sibling, _, _, physical = recompute_fixture
    error = RuntimeError('physical recompute lookup failed')
    physical.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        _recompute_field(RecomputeVisibilityProbe, field)
    assert caught.value is error
    assert RecomputeVisibilityProbe.calls == []
    assert set(env().transaction.tocompute[field]) == {31, 32, 99}
    assert set(env().transaction.tocompute[sibling]) == {31, 32, 99}


def test_compute_denial_does_not_discard_missing_work(
    recompute_fixture, monkeypatch
):
    _, _, field, sibling, _, _, _ = recompute_fixture
    error = AccessError('compute denied')
    monkeypatch.setattr(
        RecomputeVisibilityProbe, '_compute_pair', Mock(side_effect=error)
    )
    with pytest.raises(AccessError) as caught:
        _recompute_field(RecomputeVisibilityProbe, field)
    assert caught.value is error
    assert set(env().transaction.tocompute[field]) == {31, 32, 99}
    assert set(env().transaction.tocompute[sibling]) == {31, 32, 99}


def test_virtual_pending_ids_are_not_classified_as_missing(
    recompute_fixture,
):
    first, second, field, sibling, _, _, physical = recompute_fixture
    virtual = NewId()
    for computed in (field, sibling):
        env().add_to_compute(computed, [virtual, None])
    _recompute_field(RecomputeVisibilityProbe, field)
    assert set(env().transaction.tocompute[field]) == {virtual, None}
    assert set(env().transaction.tocompute[sibling]) == {virtual, None}
    physical.assert_called_once_with(pk__in=[31, 32, 99])


def test_recursive_compute_preserves_requested_order(
    recompute_fixture, monkeypatch
):
    first, second, field, _, _, _, physical = recompute_fixture
    physical.return_value = [second, first]
    monkeypatch.setattr(field, 'recursive', True)
    _recompute_field(RecomputeVisibilityProbe, field, [31, 32, 99])
    assert RecomputeVisibilityProbe.calls == [31, 32]


def test_requested_duplicate_ids_are_computed_only_once(
    recompute_fixture, monkeypatch
):
    first, second, field, _, _, _, physical = recompute_fixture
    monkeypatch.setattr(field, 'recursive', True)
    _recompute_field(RecomputeVisibilityProbe, field, [32, 31, 32, 99])
    assert RecomputeVisibilityProbe.calls == [32, 31]
