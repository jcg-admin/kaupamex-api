"""Contract for tools.config (SOL-091) — accesores MULTIDB_* (== odoo.tools.config).

Sin DB: sólo lee settings con defaults.
"""
from django.test import override_settings

from tools import config


def test_defaults():
    # Sin settings, los defaults del proyecto.
    assert config.dbfilter() == ''
    assert config.database_whitelist() is None
    assert config.management_enabled() is True
    assert config.db_charset() == 'utf8mb4'
    assert config.db_collation() == 'utf8mb4_unicode_ci'


@override_settings(
    MULTIDB_DBFILTER=r'^company_%d_db$',
    MULTIDB_DATABASE=['company_1_db'],
    MULTIDB_MANAGEMENT_ENABLED=False,
    MULTIDB_DB_CHARSET='latin1',
    MULTIDB_DB_COLLATION='latin1_swedish_ci',
)
def test_overrides():
    assert config.dbfilter() == r'^company_%d_db$'
    assert config.database_whitelist() == ['company_1_db']
    assert config.management_enabled() is False
    assert config.db_charset() == 'latin1'
    assert config.db_collation() == 'latin1_swedish_ci'
