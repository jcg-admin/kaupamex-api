"""
Tests — service.db.provision_company_database (alta unitaria idempotente, T-091-06).

Puro unitario: los helpers DDL de ``service.db`` se mockean (no se crea ninguna
base real). Verifica la orquestación: crear la base **solo si falta**, cablear
el alias runtime, y migrar **siempre** (idempotencia).
"""
from unittest import mock

import pytest

from service import db

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
