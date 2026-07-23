"""Accesores de configuración multi-DB (fiel a ``odoo.tools.config``).

Odoo lee ``config['dbfilter']`` / ``config['db_name']`` / ``config['list_db']`` /
``config['db_template']`` de su parser de config. Aquí el equivalente son las
settings ``MULTIDB_*`` de Django, centralizadas en accesores tipados para no
esparcir ``getattr(settings, ...)`` por el código (== ``odoo.tools.config`` como
punto único de acceso a la configuración).
"""
from django.conf import settings

# Charset/collation canónicos del proyecto (== ``db_setup.sh``; parte del
# ``config['db_template']`` de Odoo).
_DEFAULT_CHARSET = 'utf8mb4'
_DEFAULT_COLLATION = 'utf8mb4_unicode_ci'


def dbfilter():
    """Regex host→db (== ``config['dbfilter']``). ``''`` si no está configurado."""
    return getattr(settings, 'MULTIDB_DBFILTER', '') or ''


def database_whitelist():
    """Lista blanca de bases expuestas (== ``config['db_name']``), o ``None``."""
    return getattr(settings, 'MULTIDB_DATABASE', None)


def management_enabled():
    """¿Gestión de bases habilitada? (== ``config['list_db']``). Default ``True``."""
    return getattr(settings, 'MULTIDB_MANAGEMENT_ENABLED', True)


def db_charset():
    """Charset para ``CREATE DATABASE`` (== parte de ``config['db_template']``)."""
    return getattr(settings, 'MULTIDB_DB_CHARSET', _DEFAULT_CHARSET)


def db_collation():
    """Collation para ``CREATE DATABASE`` (acento-insensible, SOL-089)."""
    return getattr(settings, 'MULTIDB_DB_COLLATION', _DEFAULT_COLLATION)
