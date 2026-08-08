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
    assert config.db_encoding() == 'unicode'
    assert config.db_template() == 'template0'
    assert config.maintenance_db() == 'postgres'


@override_settings(
    MULTIDB_DBFILTER=r'^company_%d_db$',
    MULTIDB_DATABASE=['company_1_db'],
    MULTIDB_MANAGEMENT_ENABLED=False,
    MULTIDB_DB_ENCODING='LATIN1',
    MULTIDB_DB_TEMPLATE='template1',
    MULTIDB_MAINTENANCE_DB='otra_base',
)
def test_overrides():
    assert config.dbfilter() == r'^company_%d_db$'
    assert config.database_whitelist() == ['company_1_db']
    assert config.management_enabled() is False
    assert config.db_encoding() == 'LATIN1'
    assert config.db_template() == 'template1'
    assert config.maintenance_db() == 'otra_base'
