"""La limpieza del fixture debe respetar la adquisición exclusiva de recursos."""
import importlib.util
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def isolation_module():
    path = Path(__file__).resolve().parents[2] / 'integration/company/test_multidb_isolation.py'
    spec = importlib.util.spec_from_file_location('isolation_fixture_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('failure', [
    'existing_database', 'existing_alias', 'first_creation',
    'second_creation', 'first_migration', 'second_migration', 'cleanup',
])
def test_setup_and_cleanup_preserve_unowned_resources(isolation_module, failure):
    module = isolation_module
    aliases = ('company_771991_db', 'company_771992_db')
    databases = {'default': {}}
    if failure == 'existing_alias':
        databases[aliases[1]] = {'NAME': aliases[1]}
    with mock.patch.object(module.settings, 'DATABASES', databases), \
            mock.patch.object(module.svc, 'database_exists',
                              side_effect=lambda name: failure == 'existing_database' and name == aliases[1]), \
            mock.patch.object(module.svc, 'install_company_aliases'), \
            mock.patch.object(module.svc, 'create_empty_database') as create, \
            mock.patch.object(module.svc, 'provision_company_database') as provision, \
            mock.patch.object(module.svc, 'drop_database') as drop, \
            mock.patch.object(module, '_forget_alias') as forget:
        if failure == 'first_creation':
            create.side_effect = RuntimeError('No resource acquired')
        if failure == 'second_creation':
            create.side_effect = [None, RuntimeError('No second resource acquired')]
        if failure == 'first_migration':
            provision.side_effect = RuntimeError('Migration failed')
        if failure == 'second_migration':
            provision.side_effect = [None, RuntimeError('Migration failed')]
        if failure == 'cleanup':
            drop.side_effect = [RuntimeError('First cleanup failed'), True]
        with pytest.raises(RuntimeError):
            with module._company_databases(aliases):
                if failure != 'cleanup':
                    pytest.fail('Setup unexpectedly succeeded')
        expected = {
            'existing_database': [], 'existing_alias': [], 'first_creation': [],
            'second_creation': [aliases[0]], 'first_migration': [aliases[0]],
            'second_migration': [aliases[1], aliases[0]], 'cleanup': [aliases[1], aliases[0]],
        }[failure]
        assert drop.call_args_list == [mock.call(alias) for alias in expected]
        if failure.startswith('existing_'):
            create.assert_not_called()
            forget.assert_not_called()
        else:
            assert {call.args[0] for call in forget.call_args_list} == set(aliases)


def test_fixture_rejects_shared_default_before_access(isolation_module, monkeypatch):
    monkeypatch.setenv('CI_DATABASE_DISPOSABLE', 'kaupamex_core_qa')
    with mock.patch.object(isolation_module.settings, 'DATABASES',
                           {'default': {'NAME': 'kaupamex_core_qa'}}), \
            pytest.raises(RuntimeError, match='disposable'):
        isolation_module._require_disposable_default()
