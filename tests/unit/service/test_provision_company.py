"""
Tests — service.db.provision_company_database (alta unitaria idempotente, T-091-06).

Puro unitario: los helpers DDL de ``service.db`` se mockean (no se crea ninguna
base real). Verifica la orquestación: crear la base **solo si falta**, cablear
el alias runtime, y migrar **siempre** (idempotencia).
"""
from unittest import mock
from types import SimpleNamespace

import pytest
from django.test import override_settings

from service import db
from orm.environments import company_scope, get_current_company
from orm.routers import CompanyDatabaseRouter

pytestmark = pytest.mark.unit


def _patches():
    return (
        mock.patch.object(db, 'ensure_management_enabled'),
        mock.patch.object(db, 'create_empty_database'),
        mock.patch.object(db, 'install_company_aliases'),
        mock.patch.object(db, 'call_command'),
    )


def test_creates_base_when_absent():
    p_mgmt, p_create, p_alias, p_migrate = _patches()
    with p_mgmt, p_create as create, p_alias as alias, p_migrate as migrate, \
            mock.patch.object(db, 'database_exists', return_value=False):
        name, created = db.provision_company_database('company_7_db')

    assert (name, created) == ('company_7_db', True)
    create.assert_called_once_with('company_7_db', db.DEFAULT_DB_ALIAS)
    alias.assert_called_once()                       # alias cableado
    migrate.assert_called_once()                     # migrado
    assert migrate.call_args.kwargs['database'] == 'company_7_db'


def test_skips_create_when_present_but_migrates():
    p_mgmt, p_create, p_alias, p_migrate = _patches()
    with p_mgmt, p_create as create, p_alias as alias, p_migrate as migrate, \
            mock.patch.object(db, 'database_exists', return_value=True):
        name, created = db.provision_company_database('company_7_db')

    assert (name, created) == ('company_7_db', False)
    create.assert_not_called()                       # idempotente: no re-crea
    alias.assert_called_once()
    migrate.assert_called_once()                     # sigue migrando (nuevas migraciones)


@pytest.mark.filterwarnings('ignore:Overriding setting DATABASES:UserWarning')
@pytest.mark.parametrize('outer_company', [None, 9])
@pytest.mark.parametrize('migration_fails', [False, True])
@pytest.mark.parametrize('target', ['company_7_db', 'company_007_db'])
@override_settings(DATABASES={
    'default': {}, 'company_7_db': {}, 'company_007_db': {}, 'company_9_db': {},
})
def test_migration_uses_target_company_and_restores_outer_scope(
        outer_company, migration_fails, target):
    historical = SimpleNamespace(_meta=SimpleNamespace(
        app_label='base', model_name='iractionsreport'))
    router = CompanyDatabaseRouter()

    def migrate(*args, **kwargs):
        assert kwargs['database'] == target
        assert router.db_for_write(historical) == target
        if migration_fails:
            raise RuntimeError('migration failed after correct routing')

    p_mgmt, p_create, p_alias, p_migrate = _patches()
    original_company = get_current_company()
    with p_mgmt, p_create, p_alias, p_migrate as mocked, \
            mock.patch.object(db, 'database_exists', return_value=True):
        mocked.side_effect = migrate
        with company_scope(outer_company):
            if migration_fails:
                with pytest.raises(RuntimeError, match='migration failed after correct routing'):
                    db.provision_company_database(target)
            else:
                assert db.provision_company_database(target) == (target, False)
            assert get_current_company() == outer_company
    assert get_current_company() == original_company


def test_invalid_company_database_is_refused_before_creation():
    p_mgmt, p_create, p_alias, p_migrate = _patches()
    with p_mgmt, p_create as create, p_alias as alias, p_migrate as migrate, \
            mock.patch.object(db, 'database_exists', return_value=False):
        with pytest.raises(ValueError, match='company'):
            db.provision_company_database('unrelated_database')
    create.assert_not_called()
    alias.assert_not_called()
    migrate.assert_not_called()
