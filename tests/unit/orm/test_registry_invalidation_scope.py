"""Metadata registry flags: instance and thread scope, without SQL.

These controls do not qualify per-database model composition or the loader.
Process-level cache invalidation retains its existing separate contract.
"""

import threading
from unittest.mock import Mock

import pytest

from orm.registry import Registry, clear_cache


@pytest.fixture
def registries():
    names = ('contract_flag_first', 'contract_flag_second')
    for name in names:
        Registry.delete(name)
    first, second = (Registry(name) for name in names)
    try:
        yield first, second
    finally:
        first.cache_invalidated.clear()
        for name in names:
            Registry.delete(name)


def test_constructing_another_registry_preserves_existing_flag(registries):
    first, second = registries
    first.registry_invalidated = True
    replacement = Registry.new(second.db_name)
    assert first.registry_invalidated is True
    assert replacement.registry_invalidated is False


def test_setting_one_registry_does_not_invalidate_another(registries):
    first, second = registries
    first.registry_invalidated = True
    assert first.registry_invalidated is True
    assert second.registry_invalidated is False


def test_clearing_one_registry_preserves_anothers_flag(registries):
    first, second = registries
    first.registry_invalidated = True
    second.registry_invalidated = False
    assert first.registry_invalidated is True
    assert second.registry_invalidated is False


def test_replacing_a_registry_resets_only_its_own_flag(registries):
    first, second = registries
    first.registry_invalidated = True
    second.registry_invalidated = True
    replacement = Registry.new(first.db_name)
    assert replacement is not first
    assert replacement.registry_invalidated is False
    assert second.registry_invalidated is True


def test_flags_are_independent_in_each_thread(registries):
    first, second = registries
    first.registry_invalidated = True
    observed = []

    def read_and_write():
        observed.append((first.registry_invalidated,
                         second.registry_invalidated))
        first.registry_invalidated = True
        observed.append((first.registry_invalidated,
                         second.registry_invalidated))

    worker = threading.Thread(target=read_and_write)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert observed == [(False, False), (True, False)]
    assert first.registry_invalidated is True
    assert second.registry_invalidated is False


def test_existing_singleton_lookup_preserves_flag(registries):
    first, _second = registries
    first.registry_invalidated = True
    assert Registry(first.db_name) is first
    assert first.registry_invalidated is True


def test_shared_cache_invalidator_remains_connected(registries):
    first, second = registries
    assert first.cache_invalidated is second.cache_invalidated
    clear_cache('default')
    assert 'default' in first.cache_invalidated
    assert 'default' in second.cache_invalidated


@pytest.mark.parametrize('operation', ['signal_changes', 'reset_changes'])
def test_unflagged_consumer_preserves_another_registry(
    registries, monkeypatch, operation
):
    first, second = registries
    first.registry_invalidated = True
    second.ready = True
    cursor = Mock(side_effect=AssertionError('Unexpected SQL cursor'))
    monkeypatch.setattr(second, 'cursor', cursor)

    getattr(second, operation)()

    cursor.assert_not_called()
    assert first.registry_invalidated is True
    assert second.registry_invalidated is False


def test_reset_consumer_clears_only_its_own_flag(registries, monkeypatch):
    first, second = registries
    first.registry_invalidated = True
    second.registry_invalidated = True
    cursor = Mock()
    setup = Mock()
    monkeypatch.setattr(first, 'cursor', Mock(return_value=cursor))
    monkeypatch.setattr(first, '_setup_models__', setup)

    first.reset_changes()

    setup.assert_called_once_with(cursor)
    cursor.close.assert_called_once_with()
    cursor.execute.assert_not_called()
    assert first.registry_invalidated is False
    assert second.registry_invalidated is True
