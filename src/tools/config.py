"""Accesores de configuración multi-DB (fiel a ``odoo.tools.config``).

Odoo lee ``config['dbfilter']`` / ``config['db_name']`` / ``config['list_db']`` /
``config['db_template']`` de su parser de config. Aquí el equivalente son las
settings ``MULTIDB_*`` de Django, centralizadas en accesores tipados para no
esparcir ``getattr(settings, ...)`` por el código (== ``odoo.tools.config`` como
punto único de acceso a la configuración).
"""
from django.conf import settings

# Encoding y plantilla canónicos del proyecto (== ``config['db_template']`` de
# Odoo). Tras migrar el motor a PostgreSQL esto converge con la referencia:
# ``ENCODING 'unicode'`` + ``TEMPLATE template0``
# (``odoo19c: odoo/service/db.py:_create_empty_database``).
#
# Sustituyen a ``_DEFAULT_CHARSET``/``_DEFAULT_COLLATION`` (``utf8mb4`` /
# ``utf8mb4_unicode_ci``), que eran MariaDB-only: allá la collation
# acento-insensible hacía de ``unaccent`` (SOL-089); aquí la referencia usa la
# extensión ``unaccent``, que es lo que ``create_empty_database`` instala.
_DEFAULT_ENCODING = 'unicode'
_DEFAULT_TEMPLATE = 'template0'
_DEFAULT_MAINTENANCE_DB = 'postgres'


def dbfilter():
    """Regex host→db (== ``config['dbfilter']``). ``''`` si no está configurado."""
    return getattr(settings, 'MULTIDB_DBFILTER', '') or ''


def database_whitelist():
    """Lista blanca de bases expuestas (== ``config['db_name']``), o ``None``."""
    return getattr(settings, 'MULTIDB_DATABASE', None)


def management_enabled():
    """¿Gestión de bases habilitada? (== ``config['list_db']``). Default ``True``."""
    return getattr(settings, 'MULTIDB_MANAGEMENT_ENABLED', True)


def maintenance_db():
    """Base de mantenimiento para el DDL de bases (== ``db_connect('postgres')``).

    PostgreSQL exige estar conectado a **otra** base para crear o soltar una, y
    ``postgres`` es la que existe siempre. MariaDB no necesitaba equivalente:
    su ``CREATE DATABASE`` corría sobre la conexión actual.
    """
    return getattr(settings, 'MULTIDB_MAINTENANCE_DB', _DEFAULT_MAINTENANCE_DB)


def db_encoding():
    """Encoding para ``CREATE DATABASE`` (== ``ENCODING 'unicode'`` de Odoo)."""
    return getattr(settings, 'MULTIDB_DB_ENCODING', _DEFAULT_ENCODING)


def db_template():
    """Plantilla de ``CREATE DATABASE`` (== ``config['db_template']``).

    ``template0`` es el que permite fijar encoding/collation propios; con
    ``template1`` PostgreSQL los hereda y rechaza el override.
    """
    return getattr(settings, 'MULTIDB_DB_TEMPLATE', _DEFAULT_TEMPLATE)
