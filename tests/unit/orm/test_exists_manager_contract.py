"""Existence is independent of the public manager's visibility predicate.

The query transport is mocked explicitly; these controls do not qualify
database routing, row permissions, persistence or a native Odoo runtime.
"""

from unittest.mock import Mock

from django.db import models
import pytest

from orm.environments import Environment
from orm.identifiers import NewId
from orm.models import BaseModel


class VisibleRows(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(visible=True)


class ExistsManagerProbe(BaseModel):
    _name = 'orm.exists.manager.probe'
    _description = 'Physical existence manager contract'
    visible = models.BooleanField(default=True)
    objects = VisibleRows()
    all_rows = models.Manager()

    class Meta:
        app_label = 'contenttypes'
        managed = False
        base_manager_name = 'all_rows'
        default_manager_name = 'objects'


@pytest.fixture
def managers(monkeypatch):
    public_query = Mock()
    public_query.values_list.return_value = ()
    base_query = Mock()
    base_query.values_list.return_value = (11,)
    public = Mock(return_value=public_query)
    physical = Mock(return_value=base_query)
    monkeypatch.setattr(ExistsManagerProbe._default_manager, 'filter', public)
    monkeypatch.setattr(ExistsManagerProbe._base_manager, 'filter', physical)
    return public, physical, base_query


def records(ids):
    return ExistsManagerProbe._from_ids(Environment(), tuple(ids), tuple(ids))


def test_existing_hidden_row_survives_public_visibility_filter(managers):
    public, physical, query = managers
    result = records((11, 88)).exists()
    assert result._ids == (11,)
    public.assert_not_called()
    physical.assert_called_once_with(pk__in=(11, 88))
    query.values_list.assert_called_once_with('pk', flat=True)


def test_missing_ids_removed_without_reordering_duplicates_or_new_ids(
    managers,
):
    fresh = NewId()
    source = records((11, fresh, 88, 11))
    result = source.exists()
    assert result._ids == (11, fresh, 11)
    assert result.env is source.env


def test_only_new_records_are_returned_without_a_query(managers):
    public, physical, _ = managers
    source = records((NewId(), NewId()))
    assert source.exists() is source
    public.assert_not_called()
    physical.assert_not_called()


def test_existence_query_error_is_propagated(managers):
    _, physical, _ = managers
    physical.side_effect = RuntimeError('existence lookup failed')
    with pytest.raises(RuntimeError, match='existence lookup failed'):
        records((11,)).exists()


def test_query_cannot_add_records_outside_the_input(managers):
    _, _, query = managers
    query.values_list.return_value = (11, 99)
    assert records((11,)).exists()._ids == (11,)
