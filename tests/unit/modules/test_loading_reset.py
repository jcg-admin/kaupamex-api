"""Failure recovery must own its transaction, never finalize a live install."""
from unittest import mock

from django.db.transaction import TransactionManagementError
import pytest

from modules import loading


@pytest.mark.parametrize('atomic,autocommit', [(True, True), (False, False)])
def test_recovery_rejects_caller_transaction(atomic, autocommit):
    database = mock.Mock(in_atomic_block=atomic)
    database.get_autocommit.return_value = autocommit
    with mock.patch.object(loading, 'connections', {'recovery': database}):
        with pytest.raises(TransactionManagementError):
            loading.reset_modules_state('recovery')
    database.cursor.assert_not_called()


def test_missing_catalogue_is_noop(caplog):
    database = mock.MagicMock(in_atomic_block=False)
    database.get_autocommit.return_value = True
    database.introspection.table_names.return_value = []
    with mock.patch.object(loading, 'connections', {'recovery': database}), \
            mock.patch.object(loading.transaction, 'atomic') as atomic:
        assert loading.reset_modules_state('recovery') is None
    atomic.assert_called_once_with(using='recovery')
    database.cursor.return_value.__enter__.return_value.execute.assert_not_called()


def test_updates_are_bounded_and_errors_propagate():
    database = mock.MagicMock(in_atomic_block=False)
    database.get_autocommit.return_value = True
    database.introspection.table_names.return_value = ['ir_module_module']
    cursor = database.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = [None, RuntimeError('second update failed')]
    with mock.patch.object(loading, 'connections', {'recovery': database}), \
            mock.patch.object(loading.transaction, 'atomic') as atomic:
        with pytest.raises(RuntimeError, match='second update failed'):
            loading.reset_modules_state('recovery')
    atomic.assert_called_once_with(using='recovery')
    assert cursor.execute.call_count == 2
    assert 'to remove' in cursor.execute.call_args_list[0].args[0]
    assert 'to upgrade' in cursor.execute.call_args_list[0].args[0]
    assert 'to install' in cursor.execute.call_args_list[1].args[0]
