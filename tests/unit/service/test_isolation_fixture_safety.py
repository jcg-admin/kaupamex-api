"""A failed test fixture must not drop unowned PostgreSQL databases."""
import importlib.util
from pathlib import Path
from unittest import mock

import pytest


@pytest.mark.parametrize('failure', ['preexisting', 'create_failed', 'migration_failed'])
def test_setup_failure_drops_only_successfully_created_resources(failure):
    path = Path(__file__).resolve().parents[2]/'integration/company/test_multidb_isolation.py'
    spec = importlib.util.spec_from_file_location('isolation_fixture_contract', path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    blocker = mock.MagicMock()
    with mock.patch.object(fixture.settings, 'DATABASES', {'default': {}}), \
            mock.patch.object(fixture.svc, 'database_exists', return_value=failure == 'preexisting'), \
            mock.patch.object(fixture.svc, 'install_company_aliases'), \
            mock.patch.object(fixture.svc, 'create_empty_database') as create, \
            mock.patch.object(fixture.svc, 'provision_company_database') as provision, \
            mock.patch.object(fixture, 'call_command', create=True) as legacy_migrate, \
            mock.patch.object(fixture.svc, 'drop_database') as drop, \
            mock.patch.object(fixture, '_forget_alias'):
        if failure in ['preexisting', 'create_failed']:
            create.side_effect = RuntimeError('Creation did not acquire resource')
        else:
            provision.side_effect = RuntimeError('Migration failed after creation')
            legacy_migrate.side_effect = RuntimeError('Migration failed after creation')
        generator = fixture.two_company_databases.__wrapped__(blocker)
        with pytest.raises(RuntimeError):
            next(generator)
        if failure == 'migration_failed':
            drop.assert_called_once_with(fixture._ALIAS_A)
        else:
            drop.assert_not_called()
        if failure == 'preexisting':
            create.assert_not_called()
