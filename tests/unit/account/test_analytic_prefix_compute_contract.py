"""Actual analytic descriptor behavior with account reads explicitly mocked.

No database is used; these controls do not accept analytic persistence,
active-company equivalence or the complete recomputation graph.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from addons.account.models import account_analytic_distribution_model as addon
from addons.analytic.models.analytic_distribution_model import (
    AccountAnalyticDistributionModel,
)
from orm.environments import env as get_environment


@pytest.fixture
def prefix_field():
    field = AccountAnalyticDistributionModel._meta.get_field(
        'prefix_placeholder'
    )
    cache = field._get_cache(get_environment())
    cache.clear()
    yield field
    cache.clear()


@pytest.fixture
def accounts(monkeypatch):
    queryset = Mock()
    queryset.filter.return_value = queryset
    queryset.order_by.return_value = queryset
    select = Mock(return_value=queryset)
    monkeypatch.setattr(addon.AccountAccount.objects, 'filter', select)
    return select, queryset


def test_prefix_is_computed_without_a_default_or_column(prefix_field):
    assert callable(prefix_field.compute)
    assert not prefix_field.has_default()
    assert prefix_field.store is False
    assert prefix_field.column is None
    assert prefix_field.concrete is False


@pytest.mark.parametrize(
    'code,expected',
    [(None, '60, 61, 62'), ('', '60, 61, 62'),
     ('ABC', '60, 61, 62'), ('550100', '55, 56, 57')],
)
def test_new_record_reads_the_assigned_compute_value(
    prefix_field, accounts, code, expected
):
    select, queryset = accounts
    queryset.first.return_value = (
        SimpleNamespace(code=code) if code is not None else None
    )
    record = AccountAnalyticDistributionModel(company_id=11)

    assert record.prefix_placeholder == 'e.g. ' + expected
    assert record.pk is None
    select.assert_called_once_with(account_type='expense')
    queryset.filter.assert_called_once_with(company=11)
    queryset.order_by.assert_called_once_with('code')


def test_distinct_new_records_cannot_share_a_computed_prefix(
    prefix_field, accounts
):
    _, queryset = accounts
    queryset.first.side_effect = [
        SimpleNamespace(code='550100'), SimpleNamespace(code='700100'),
    ]
    first = AccountAnalyticDistributionModel(company_id=11)
    second = AccountAnalyticDistributionModel(company_id=22)

    assert first.prefix_placeholder == 'e.g. 55, 56, 57'
    assert second.prefix_placeholder == 'e.g. 70, 71, 72'
    assert first.prefix_placeholder == 'e.g. 55, 56, 57'
    assert first.pk is None and second.pk is None
    assert queryset.first.call_count == 2


def test_compute_must_assign_instead_of_returning_a_value(
    prefix_field, monkeypatch
):
    monkeypatch.setattr(prefix_field, 'compute', lambda record: 'ignored')
    with pytest.raises(ValueError, match='failed to assign'):
        _ = AccountAnalyticDistributionModel().prefix_placeholder
