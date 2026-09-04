"""Accesores de configuración multi-DB (fiel a ``odoo.tools.config``).

Odoo lee ``config['dbfilter']`` / ``config['db_name']`` / ``config['list_db']`` /
``config['db_template']`` de su parser de config. Aquí el equivalente son las
settings ``MULTIDB_*`` de Django, centralizadas en accesores tipados para no
esparcir ``getattr(settings, ...)`` por el código (== ``odoo.tools.config`` como
punto único de acceso a la configuración).
"""
from pathlib import Path

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


def root_path():
    """Raíz del paquete del producto — ≙ ``config.root_path`` de la referencia.

    Allá es el directorio del paquete ``odoo/``; aquí es ``src/``, que es la
    misma relación (ver el comentario de ``modules.module.ADDONS_PATHS``, donde
    esa correspondencia ya se declara). La consume el cargador de datos para
    localizar ``import_xml.rng``, igual que ``convert_xml_import`` allá.
    """
    return str(Path(__file__).resolve().parent.parent)


def test_enable():
    """≙ ``config['test_enable']`` — ¿corre la aplicación bajo pruebas?

    La fuente lo lee de su bandera de línea de comandos; aquí el equivalente
    es que el módulo de settings cargado sea el de pruebas
    (``config.settings.testing``), que es la única forma en que este árbol
    entra en modo de prueba.
    """
    return settings.SETTINGS_MODULE.endswith('.testing')


def dev_mode():
    """≙ ``config['dev_mode']`` — la lista de modos de desarrollo activos.

    La fuente la puebla desde ``--dev=qweb,reload,…``; aquí la única fuente de
    verdad del modo de desarrollo es ``DEBUG``, así que la lista es ``['qweb']``
    con ``DEBUG`` encendido y vacía en producción. Se devuelve una lista y no
    un booleano para conservar el contrato (``'qweb' in config['dev_mode']``).
    """
    return ['qweb'] if settings.DEBUG else []


def bin_path():
    """≙ ``config['bin_path']`` — directorio extra donde buscar binarios externos.

    La fuente lo añade al ``PATH`` heredado antes de resolver un ejecutable
    (``odoo19c: odoo/tools/misc.py:find_in_path``), para el despliegue donde el
    binario auxiliar no vive en una ruta del sistema. Aquí el equivalente es la
    setting ``BIN_PATH``; vacía significa "sólo el ``PATH`` del proceso".
    """
    return getattr(settings, 'BIN_PATH', '') or ''


def pg_path():
    """≙ ``config['pg_path']`` — directorio de las herramientas de PostgreSQL.

    Gobierna dónde se busca ``pg_dump``/``pg_restore``
    (``odoo19c: odoo/tools/misc.py:find_pg_tool``). Con un cluster instalado por
    el gestor de paquetes los binarios están en el ``PATH`` y esta setting sobra;
    hace falta cuando conviven varias versiones de PostgreSQL y el volcado debe
    salir de una en concreto — un ``pg_dump`` más viejo que el servidor rehúsa
    con ``server version mismatch``.
    """
    return getattr(settings, 'PG_PATH', '') or ''
