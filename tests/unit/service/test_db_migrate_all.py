"""Unit tests de ``migrate_all_company_databases`` (SOL-091, T-091-06).

Prueba la **orquestación** del loop de migración multi-base: acumulación de
resultado por-base (``ok``/``failed``), no-abort ante fallo parcial, guard de
gestión y default de nombres por descubrimiento. El primitivo subyacente
(``call_command('migrate', database=alias)``) es Django-nativo y se **mockea**
aquí — lo novedoso es el loop y su resiliencia, no la migración en sí (que
mejora sobre Odoo, que aborta al primer fallo).
"""
from unittest import mock

import pytest

from service.db import (
    DatabaseManagementDisabled,
    migrate_all_company_databases,
)


@mock.patch('service.db.call_command')
@mock.patch('service.db._ensure_alias_registered')
@mock.patch('service.db.config')
def test_migrate_all_ok(mock_config, mock_reg, mock_call):
    mock_config.management_enabled.return_value = True
    res = migrate_all_company_databases(names=['company_1_db', 'company_2_db'])
    assert res == [
        {'db': 'company_1_db', 'status': 'ok', 'error': None},
        {'db': 'company_2_db', 'status': 'ok', 'error': None},
    ]
    assert mock_call.call_count == 2


@mock.patch('service.db.call_command')
@mock.patch('service.db._ensure_alias_registered')
@mock.patch('service.db.config')
def test_migrate_all_partial_failure_does_not_abort(mock_config, mock_reg, mock_call):
    mock_config.management_enabled.return_value = True
    # La segunda base falla; las otras dos deben migrarse igual (no-abort).
    mock_call.side_effect = [None, RuntimeError('boom en company_2'), None]
    res = migrate_all_company_databases(
        names=['company_1_db', 'company_2_db', 'company_3_db'])
    assert res[0] == {'db': 'company_1_db', 'status': 'ok', 'error': None}
    assert res[1]['db'] == 'company_2_db'
    assert res[1]['status'] == 'failed'
    assert 'boom en company_2' in res[1]['error']
    assert res[2] == {'db': 'company_3_db', 'status': 'ok', 'error': None}
    assert mock_call.call_count == 3


@mock.patch('service.db.call_command')
@mock.patch('service.db.config')
def test_migrate_all_management_disabled_raises_before_loop(mock_config, mock_call):
    mock_config.management_enabled.return_value = False
    with pytest.raises(DatabaseManagementDisabled):
        migrate_all_company_databases(names=['company_1_db'])
    mock_call.assert_not_called()


@mock.patch('service.db.call_command')
@mock.patch('service.db._ensure_alias_registered')
@mock.patch('service.db.config')
@mock.patch('service.db.list_company_db_names')
def test_migrate_all_default_names_from_discovery(
        mock_list, mock_config, mock_reg, mock_call):
    mock_config.management_enabled.return_value = True
    mock_list.return_value = ['company_7_db']
    res = migrate_all_company_databases()  # names=None → descubre existentes
    mock_list.assert_called_once()
    assert [r['db'] for r in res] == ['company_7_db']
    assert mock_call.call_count == 1
