"""Contract for service.db pure logic (SOL-091, T-091-06).

Adaptación de ``odoo/service/db.py``: quoting de identificadores
(``database_identifier``) y guard de gestión (``check_db_management_enabled``).
Sin DB — las ops de DDL vivas están en tests/integration/orm/test_provision.py.
"""
import pytest
from django.test import override_settings

from service.db import (
    DatabaseManagementDisabled,
    ensure_management_enabled,
    quote_db_identifier,
)


def test_quote_accepts_company_db_name():
    assert quote_db_identifier('company_5_db') == '`company_5_db`'


@pytest.mark.parametrize('bad', [
    'company_5_db; DROP DATABASE x',   # inyección
    'company-5-db',                    # guion no permitido
    'company 5 db',                    # espacios
    'company`_db',                     # backtick
    '',                                # vacío
    None,                              # None
])
def test_quote_rejects_unsafe_identifiers(bad):
    with pytest.raises(ValueError):
        quote_db_identifier(bad)


def test_management_enabled_by_default():
    # Sin la setting, la gestión está habilitada (no lanza).
    ensure_management_enabled()


@override_settings(MULTIDB_MANAGEMENT_ENABLED=False)
def test_management_can_be_disabled():
    with pytest.raises(DatabaseManagementDisabled):
        ensure_management_enabled()
