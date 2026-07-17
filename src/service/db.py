"""Servicio de bases DB-per-company (SOL-091, Palanca B) — ``service/db.py``.

Adaptación **fiel** de la capa de bases de Odoo 19 a Django/MariaDB. En Odoo esta
funcionalidad se reparte en tres módulos **hermanos de ``orm/``** bajo ``odoo/``;
a nuestra escala se consolidan aquí (documentado), manteniendo el nivel
**service** (no dentro de ``orm/``, que sólo tiene el binding ORM↔base):

- ``odoo/service/db.py`` — administración de bases (create/drop/duplicate/rename/
  exist/list/dump). Es el núcleo de este módulo.
- ``odoo/http.py`` — resolución de base por request (``db_filter``/``db_list``).
- ``odoo/sql_db.py`` — capa de conexión (``connection_info_for``/``close_db``/
  ``close_all``). En Django la conexión por base es ``connections[alias]``; sólo
  reimplementamos la composición del dict de conexión y el cierre.

Odoo ejecuta el DDL de servidor vía una conexión de mantenimiento a la base
``postgres``; MariaDB no tiene esa base — usamos ``connections[using]`` (por
defecto ``default`` = plano de control L0) con el grant ``company\\_%`` (T-091-01,
``db_setup.sh``). El DDL en MariaDB es no transaccional y auto-commitea
(F-DJ-03, ``@@autocommit=1``): no hace falta el ``rollback()`` + ``autocommit``
que Odoo fuerza en PostgreSQL.

Divergencias MariaDB vs PostgreSQL: ``CREATE DATABASE ... TEMPLATE`` (duplicado)
y ``RENAME DATABASE`` no existen en MariaDB → se adaptan con
``mariadb-dump | mariadb`` y con duplicate+drop respectivamente.
"""
import copy
import re
import shutil
import subprocess

from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections

from tools import config


class DatabaseManagementDisabled(Exception):
    """== ``AccessDenied`` de ``check_db_management_enabled`` en Odoo."""


class DatabaseExists(Exception):
    """== ``DatabaseExists`` de ``_create_empty_database`` en Odoo."""


# Forma canónica del nombre de base de empresa (== ``routers.company_db_alias``).
_COMPANY_DB_RE = re.compile(r'^company_\d+_db$')
# Identificador seguro para DDL (más estricto que ``quote_ident`` de Odoo).
_IDENTIFIER_RE = re.compile(r'^[A-Za-z0-9_]+$')


# ---------------------------------------------------------------------------
# Composición de la conexión (== ``sql_db.connection_info_for``)
# ---------------------------------------------------------------------------

def build_company_alias(base_default, db_name):
    """Clona ``base_default`` cambiando ``NAME`` = ``db_name`` (== ``connection_info_for``).

    Deep copy para que ``OPTIONS`` (socket) del clon no comparta referencia con
    el ``default`` — mutar uno no debe afectar al otro (F-DJ-02: cada entrada de
    ``DATABASES`` debe ser un dict completo).
    """
    entry = copy.deepcopy(base_default)
    entry['NAME'] = db_name
    return entry


def build_company_databases(db_names, base_default):
    """Devuelve ``{alias: settings}`` — un alias por base de empresa.

    El alias Django **es** el ``db_name`` (``company_<N>_db``), igual que el
    router. Con ``db_names`` vacío (N=1) devuelve ``{}`` — ``DATABASES`` queda
    sólo con ``default``.
    """
    return {name: build_company_alias(base_default, name) for name in db_names}


def install_company_aliases(databases, names=None, using=DEFAULT_DB_ALIAS):
    """Loader T-091-05: puebla el dict ``DATABASES`` con un alias por base
    ``company_<N>_db`` (== ``connection_info_for`` de cada base al boot).

    ``names`` explícito (roster de ``settings``, 12-factor) **no** consulta la
    DB — safe en el import de ``settings`` (chicken-and-egg con ``connections``;
    una DB fresca/CI aún no existe). ``names=None`` descubre por
    ``information_schema`` (``list_company_db_names``): uso **runtime**, no en
    settings-import. Con roster vacío (N=1) es no-op: ``DATABASES`` queda con
    ``default``. Idempotente (no re-crea aliases ya presentes). Muta y devuelve
    el propio ``databases``.
    """
    if names is None:
        names = list_company_db_names(using)
    base_default = databases[using]
    for name in names:
        if name not in databases:
            databases[name] = build_company_alias(base_default, name)
    return databases


# ---------------------------------------------------------------------------
# Descubrimiento de bases (== ``service/db.list_dbs`` sobre ``pg_database``)
# ---------------------------------------------------------------------------

def list_all_schema_names(using=DEFAULT_DB_ALIAS):
    """Todos los schemas del motor (== ``list_dbs``: ``pg_database`` → SCHEMATA)."""
    with connections[using].cursor() as cursor:
        cursor.execute(
            'SELECT SCHEMA_NAME FROM information_schema.SCHEMATA '
            'ORDER BY SCHEMA_NAME'
        )
        return [row[0] for row in cursor.fetchall()]


def filter_company_dbs(names, pattern=_COMPANY_DB_RE):
    """Filtra los schemas con forma ``company_<N>_db`` (guard de forma propio).

    Función pura: descarta los del sistema (``mysql``, …) y el plano L0
    (``kaupamex_db``), preservando el orden.
    """
    return [n for n in names if pattern.match(n)]


def list_company_db_names(using=DEFAULT_DB_ALIAS):
    """Bases de empresa existentes: fetch + filtro de forma ``company_<N>_db``."""
    return filter_company_dbs(list_all_schema_names(using))


# ---------------------------------------------------------------------------
# Resolución por host (== ``http.db_filter`` / ``http.db_list``)
# ---------------------------------------------------------------------------

def db_filter(dbs, host, dbfilter=None, db_name=None):
    """Subconjunto de ``dbs`` que matchea el ``dbfilter`` o la whitelist por host.

    Adaptación fiel de ``odoo/http.py::db_filter``:

    - Con regex ``dbfilter``: normaliza el host (quita ``:puerto`` y ``www.``),
      ``domain = host.partition('.')[0]``, sustituye ``%h`` = host y ``%d`` =
      domain (``re.escape``) y devuelve las bases cuyo **nombre** matchea.
    - Sin ``dbfilter`` pero con ``db_name`` (whitelist ``--database``):
      intersección ordenada.
    - Sin ninguno: ``dbs`` tal cual.

    Función **pura**. ``dbfilter``/``db_name`` salen de ``settings``
    (``MULTIDB_DBFILTER`` / ``MULTIDB_DATABASE``) cuando no se pasan. El
    **mecanismo** vive aquí; la **política** (regex subdominio→``company_<N>``)
    la fija el resolver host→company (UC-PLT-06).
    """
    if dbfilter is None:
        dbfilter = config.dbfilter()
    if db_name is None:
        db_name = config.database_whitelist()

    if dbfilter:
        host = (host or '').partition(':')[0]
        if host.startswith('www.'):
            host = host[4:]
        domain = host.partition('.')[0]
        dbfilter_re = re.compile(
            dbfilter.replace('%h', re.escape(host)).replace('%d', re.escape(domain))
        )
        return [db for db in dbs if dbfilter_re.match(db)]

    if db_name:
        return sorted(set(db_name).intersection(dbs))

    return list(dbs)


def db_list_for_host(host, using=DEFAULT_DB_ALIAS):
    """Bases de empresa expuestas para un ``host`` (== ``http.db_list``).

    ``db_filter(list_company_db_names(), host)`` — el mismo compuesto que Odoo
    ``db_list`` = ``db_filter(list_dbs(), host)``.
    """
    return db_filter(list_company_db_names(using), host)


def db_monodb(host, using=DEFAULT_DB_ALIAS):
    """La **única** base expuesta para un ``host``, o ``None`` (helper derivado).

    Reproduce el patrón histórico ``http.db_monodb`` (**removido** en Odoo 18/19;
    aquí es un helper propio derivado de ``db_list``, no un port vigente).
    """
    dbs = db_list_for_host(host, using)
    return dbs[0] if len(dbs) == 1 else None


# ---------------------------------------------------------------------------
# Ciclo de vida de conexiones (== ``sql_db.close_db`` / ``sql_db.close_all``)
# ---------------------------------------------------------------------------

def close_db(alias):
    """Cierra la conexión Django de un alias si está configurada (== ``close_db``).

    Guard: sólo cierra si el alias está en ``settings.DATABASES`` (evita
    ``ConnectionDoesNotExist`` para bases no cargadas). No-op si no existe.
    """
    if alias in connections:
        connections[alias].close()


def close_all():
    """Cierra todas las conexiones Django (== ``sql_db.close_all``)."""
    connections.close_all()


# ---------------------------------------------------------------------------
# Administración de bases (== ``service/db.py`` exp_*)
# ---------------------------------------------------------------------------

def quote_db_identifier(name):
    """Valida y backtick-cita un identificador de base (== ``database_identifier``).

    Nuestras bases son ``company_<N>_db``; validar contra ``^[A-Za-z0-9_]+$`` es
    más estricto que ``quote_ident`` de Odoo e imposibilita la inyección en el
    DDL (``CREATE``/``DROP DATABASE`` no admiten placeholders).
    """
    if not _IDENTIFIER_RE.match(name or ''):
        raise ValueError('identificador de base invalido: %r' % (name,))
    return '`%s`' % name


def ensure_management_enabled():
    """Guard == ``check_db_management_enabled`` (Odoo ``config['list_db']``)."""
    if not config.management_enabled():
        raise DatabaseManagementDisabled(
            'gestion de bases multi-DB deshabilitada (MULTIDB_MANAGEMENT_ENABLED)')


def database_exists(db_name, using=DEFAULT_DB_ALIAS):
    """== ``exp_db_exist``: ¿existe la base? (catálogo ``information_schema``)."""
    with connections[using].cursor() as cursor:
        cursor.execute(
            'SELECT 1 FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s',
            [db_name],
        )
        return cursor.fetchone() is not None


def create_empty_database(db_name, using=DEFAULT_DB_ALIAS):
    """== ``_create_empty_database``: ``CREATE DATABASE`` charset/collation utf8mb4.

    Si existe → ``DatabaseExists``. **Sin extensiones** (``pg_trgm``/``unaccent``
    no existen en MariaDB; el unaccent se resuelve con collation ``_ci`` +
    ``REGEXP``, SOL-089).
    """
    ensure_management_enabled()
    if database_exists(db_name, using):
        raise DatabaseExists('la base %r ya existe' % (db_name,))
    ident = quote_db_identifier(db_name)
    with connections[using].cursor() as cursor:
        cursor.execute(
            'CREATE DATABASE %s CHARACTER SET %s COLLATE %s'
            % (ident, config.db_charset(), config.db_collation())
        )


def kill_connections(db_name, using=DEFAULT_DB_ALIAS):
    """== ``_drop_conn``: termina conexiones a la base (best-effort).

    MariaDB: ``KILL`` sobre ``information_schema.PROCESSLIST`` filtrando por
    ``DB`` y excluyendo ``CONNECTION_ID()`` (== ``pg_terminate_backend`` de Odoo).
    """
    with connections[using].cursor() as cursor:
        cursor.execute(
            'SELECT ID FROM information_schema.PROCESSLIST '
            'WHERE DB = %s AND ID != CONNECTION_ID()',
            [db_name],
        )
        ids = [row[0] for row in cursor.fetchall()]
        for pid in ids:
            try:
                cursor.execute('KILL CONNECTION %d' % int(pid))
            except Exception:
                pass


def drop_database(db_name, using=DEFAULT_DB_ALIAS):
    """== ``exp_drop``: cierra conexiones + ``DROP DATABASE``. ``False`` si no existía."""
    ensure_management_enabled()
    if not database_exists(db_name, using):
        return False
    close_db(db_name)
    kill_connections(db_name, using)
    ident = quote_db_identifier(db_name)
    with connections[using].cursor() as cursor:
        cursor.execute('DROP DATABASE %s' % ident)
    return True


def create_database(db_name, using=DEFAULT_DB_ALIAS):
    """== ``exp_create_database``: crear vacía + inicializar (``migrate``).

    Nuestro "initialize" = ``migrate --database=<alias>`` (las apps Django son los
    "módulos"). Requiere que ``db_name`` sea un alias en ``settings.DATABASES``
    (loader T-091-05). Devuelve el nombre creado.
    """
    ensure_management_enabled()
    create_empty_database(db_name, using)
    call_command('migrate', database=db_name, run_syncdb=True, verbosity=0)
    return db_name


def _resolve_bin(*candidates):
    """Primer binario disponible (MariaDB 11.8 quitó ``mysqldump``/``mysql``;
    quedan ``mariadb-dump``/``mariadb``)."""
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError('binario no encontrado: %s' % (candidates,))


def _mysql_conn_args(alias):
    """Flags de conexión (socket/host/port/user/pass) del alias, para los
    binarios externos (== Odoo delega en ``pg_dump``/``pg_restore``)."""
    sd = connections[alias].settings_dict
    opts = sd.get('OPTIONS', {}) or {}
    args = ['-u', sd['USER']]
    if sd.get('PASSWORD'):
        args.append('-p%s' % sd['PASSWORD'])
    if opts.get('unix_socket'):
        args += ['--socket=%s' % opts['unix_socket']]
    else:
        if sd.get('HOST'):
            args += ['-h', sd['HOST']]
        if sd.get('PORT'):
            args += ['-P', str(sd['PORT'])]
    return args


def duplicate_database(src_name, dst_name, using=DEFAULT_DB_ALIAS):
    """== ``exp_duplicate_database``: copia ``src`` → ``dst``.

    MariaDB **no tiene** ``CREATE DATABASE ... TEMPLATE``: se crea la destino
    vacía y se copia schema + datos con ``mariadb-dump src | mariadb dst``.
    """
    ensure_management_enabled()
    if not database_exists(src_name, using):
        raise ValueError('la base origen %r no existe' % (src_name,))
    create_empty_database(dst_name, using)
    conn_args = _mysql_conn_args(using)
    dump_bin = _resolve_bin('mariadb-dump', 'mysqldump')
    client_bin = _resolve_bin('mariadb', 'mysql')
    # --single-transaction: snapshot InnoDB consistente sin ``LOCK TABLES`` (que
    # el grant mínimo company_% no incluye). Se copian tablas + datos; las bases
    # de empresa son schemas Django (sin routines/events server-side).
    # --single-transaction: snapshot InnoDB sin ``LOCK TABLES`` en el origen.
    # --skip-add-locks: que el volcado NO emita ``LOCK TABLES`` alrededor de los
    # INSERT — el grant mínimo company_% no incluye LOCK TABLES en el destino.
    dump = subprocess.Popen(
        [dump_bin, *conn_args, '--single-transaction', '--skip-lock-tables',
         '--skip-add-locks', src_name],
        stdout=subprocess.PIPE,
    )
    load = subprocess.Popen([client_bin, *conn_args, dst_name], stdin=dump.stdout)
    dump.stdout.close()
    load.communicate()
    if load.returncode != 0 or dump.wait() != 0:
        drop_database(dst_name, using)
        raise RuntimeError('duplicado %r -> %r fallo' % (src_name, dst_name))
    return dst_name


def rename_database(old_name, new_name, using=DEFAULT_DB_ALIAS):
    """== ``exp_rename``: renombra ``old`` → ``new``.

    MariaDB **eliminó** ``RENAME DATABASE`` (era peligroso): se adapta con
    ``duplicate`` + ``drop`` (el patrón recomendado en MariaDB).
    """
    ensure_management_enabled()
    duplicate_database(old_name, new_name, using)
    drop_database(old_name, using)
    return new_name


def _ensure_alias_registered(name, base_default):
    """Registra el alias de empresa en ``connections.databases`` si falta.

    Loader **self-contained**: no depende de que el settings-loader
    (``DATABASE_ROUTERS`` dinámico, T-091-05) esté cableado — clona
    ``base_default`` cambiando ``NAME`` y lo inyecta en el handler vivo para que
    ``call_command('migrate', database=name)`` resuelva. Idempotente.
    """
    if name not in connections.databases:
        connections.databases[name] = build_company_alias(base_default, name)


def migrate_all_company_databases(names=None, using=DEFAULT_DB_ALIAS):
    """== ``exp_migrate_databases``: aplica migraciones a N bases de empresa.

    Odoo recrea el ``Registry`` con ``update_module=True`` por cada base y
    **aborta el loop al primer fallo** (``service/db.py:413-418``). Aquí
    mejoramos la resiliencia: se acumula el resultado **por base** y **nunca**
    se aborta ante un fallo parcial — una base rota no impide migrar el resto.
    El primitivo por base es el mismo ``migrate --database=<alias>`` que
    ``create_database`` usa una vez.

    ``names=None`` → descubre las bases ``company_<N>_db`` existentes
    (``list_company_db_names``). Es un **loop autocontenido**: registra el alias
    de cada base antes de migrarla. Devuelve
    ``[{'db': name, 'status': 'ok'|'failed', 'error': str|None}, ...]``.
    """
    ensure_management_enabled()
    if names is None:
        names = list_company_db_names(using)
    base_default = connections[using].settings_dict
    results = []
    for name in names:
        try:
            _ensure_alias_registered(name, base_default)
            call_command('migrate', database=name, run_syncdb=True, verbosity=0)
            results.append({'db': name, 'status': 'ok', 'error': None})
        except Exception as exc:  # noqa: BLE001
            # Acumular por-base y CONTINUAR (mejora sobre el abort de Odoo): el
            # error queda en el resultado, no se traga en silencio.
            results.append({'db': name, 'status': 'failed', 'error': str(exc)})
    return results
