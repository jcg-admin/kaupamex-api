"""Requested-name validation is read-only and bound to its supplied cursor."""
from unittest import mock

import pytest

from modules import loading


@pytest.mark.parametrize('names', [[], ['all'], ['all', 'all']])
def test_empty_or_wildcard_does_not_query(names):
    cursor = mock.Mock()
    assert loading._check_module_names(cursor, names) is None
    cursor.execute.assert_not_called()


def test_known_duplicates_and_generator_are_not_reported(caplog):
    cursor = mock.Mock()
    cursor.fetchone.return_value = (2,)
    assert loading._check_module_names(
        cursor, (name for name in ['base', 'all', 'sale', 'base'])) is None
    assert cursor.execute.call_count == 1
    query, parameters = cursor.execute.call_args.args
    assert 'count(id)' in query and set(parameters[0]) == {'base', 'sale'}
    cursor.fetchall.assert_not_called()
    assert not caplog.records


def test_unknown_names_are_warned_once_without_writes(caplog):
    cursor = mock.Mock()
    cursor.fetchone.return_value = (1,)
    cursor.fetchall.return_value = [('base',), ('stock',)]
    assert loading._check_module_names(
        cursor, ['base', 'unknown_contract', 'unknown_contract', 'all']) is None
    assert [r.getMessage() for r in caplog.records] == [
        'invalid module names, ignored: unknown_contract']
    assert cursor.execute.call_count == 2
    assert all(call.args[0].startswith('SELECT ') for call in cursor.execute.call_args_list)


def test_catalogue_errors_propagate():
    cursor = mock.Mock()
    cursor.execute.side_effect = RuntimeError('catalogue unavailable')
    with pytest.raises(RuntimeError, match='catalogue unavailable'):
        loading._check_module_names(cursor, ['base'])
