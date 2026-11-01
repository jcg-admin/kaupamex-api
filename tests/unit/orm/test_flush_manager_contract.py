"""Physical flush IDs are independent of a public visibility filter.

Query transport and save are explicit mocks. Actual PostgreSQL M2M commit
controls complement these cases; no row-permission acceptance is implied.
"""

from unittest.mock import Mock

from django.db import models
import pytest

import fields
from exceptions import AccessError
from orm import registry
from orm.environments import env, transaction_scope
from orm.models import _flush


class VisibleFlushRows(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(visible=True)


class FlushManagerProbe(models.Model):
    _name = 'orm.flush.manager.probe'
    visible = models.BooleanField(default=True)
    value = fields.Char(max_length=32)
    objects = VisibleFlushRows()
    physical_rows = models.Manager()

    class Meta:
        app_label = 'contenttypes'
        managed = False
        base_manager_name = 'physical_rows'
        default_manager_name = 'objects'


@pytest.fixture
def flush_fixture(monkeypatch):
    with transaction_scope():
        registry.clear_field_depends()
        first = FlushManagerProbe(pk=31, visible=True, value='before')
        second = FlushManagerProbe(pk=32, visible=False, value='before')
        first.save = Mock()
        second.save = Mock()
        field = FlushManagerProbe._meta.get_field('value')
        field._update_cache((31, 32), 'after', dirty=True)
        public = Mock(return_value=[first])
        physical = Mock(return_value=[first, second])
        monkeypatch.setattr(FlushManagerProbe.objects, 'filter', public)
        monkeypatch.setattr(
            FlushManagerProbe._base_manager, 'filter', physical
        )
        yield first, second, field, public, physical
        registry.clear_field_depends()


def test_hidden_existing_dirty_row_is_written(flush_fixture):
    first, second, field, public, physical = flush_fixture
    _flush(FlushManagerProbe.objects.none())
    first.save.assert_called_once_with(update_fields=['value'])
    second.save.assert_called_once_with(update_fields=['value'])
    assert first.__dict__['value'] == second.__dict__['value'] == 'after'
    assert not env().transaction.field_dirty.get(field)
    public.assert_not_called()
    physical.assert_called_once_with(pk__in=[31, 32])


def test_physically_missing_row_is_not_recreated(flush_fixture):
    first, second, field, public, physical = flush_fixture
    physical.return_value = [first]
    _flush(FlushManagerProbe.objects.none())
    first.save.assert_called_once_with(update_fields=['value'])
    second.save.assert_not_called()
    assert not env().transaction.field_dirty.get(field)


def test_physical_lookup_error_is_not_reported_as_success(flush_fixture):
    first, second, field, public, physical = flush_fixture
    error = RuntimeError('physical lookup failed')
    physical.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        _flush(FlushManagerProbe.objects.none())
    assert caught.value is error
    first.save.assert_not_called()
    second.save.assert_not_called()


def test_existing_write_denial_still_propagates(flush_fixture):
    first, second, field, public, physical = flush_fixture
    error = AccessError('write denied')
    first.save.side_effect = error
    with pytest.raises(AccessError) as caught:
        _flush(FlushManagerProbe.objects.none())
    assert caught.value is error
    second.save.assert_not_called()
