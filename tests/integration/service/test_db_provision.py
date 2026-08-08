"""Provisioning DB-per-company contra MariaDB real (SOL-091, T-091-06).

Ejercita las ops de ``odoo/service/db.py`` adaptadas (``service.db``) contra
el motor: ``CREATE``/``DROP DATABASE``, existencia por catálogo, kill de
conexiones, duplicado (``mariadb-dump | mariadb``), rename (duplicate+drop) e
inicialización (``migrate --database``). Requiere el grant ``company\\_%``
(T-091-01, ``db_setup.sh``): sin él el motor devuelve 1044 y estos tests fallan
— es la señal correcta de que el provisioning no está habilitado.
"""
import pytest
from django.db import connections
from django.test import override_settings

from service.db import (
    DatabaseExists,
    _connect,
    DatabaseManagementDisabled,
    create_database,
    create_empty_database,
    database_exists,
    db_monodb,
    drop_database,
    duplicate_database,
    kill_connections,
    closing_cursor,
    rename_database,
)

# transaction=True: el DDL (CREATE/DROP DATABASE) auto-commitea en MariaDB y
# rompería el wrapper transaccional de un django_db normal. databases='__all__':
# estas pruebas tocan bases company_* dinámicas fuera de 'default'.
pytestmark = pytest.mark.django_db(transaction=True, databases='__all__')

# Nombres fuera del rango real (company_1..N); 90xx evita colisión con datos.
DB_A = 'company_9001_db'
DB_B = 'company_9002_db'
DB_C = 'company_9003_db'
ALL = [DB_A, DB_B, DB_C]


@pytest.fixture(autouse=True)
def _clean_company_dbs():
    # Pre y post: dejar el motor sin las bases de prueba (idempotencia).
    for name in ALL:
        if database_exists(name):
            drop_database(name)
    yield
    for name in ALL:
        if database_exists(name):
            drop_database(name)


def test_database_exists_catalog():
    # El schema de la conexión default existe; uno inventado, no.
    assert database_exists(connections['default'].settings_dict['NAME']) is True
    assert database_exists('company_does_not_exist_db') is False


def test_create_then_drop():
    assert database_exists(DB_A) is False
    create_empty_database(DB_A)
    assert database_exists(DB_A) is True
    # ENCODING aplicado. El catálogo es ``pg_database``, y el encoding se lee
    # con ``pg_encoding_to_char`` porque la columna guarda su id numérico.
    with connections['default'].cursor() as c:
        c.execute(
            'SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname = %s',
            [DB_A])
        (encoding,) = c.fetchone()
    assert encoding == 'UTF8'
    assert drop_database(DB_A) is True
    assert database_exists(DB_A) is False


def test_create_twice_raises():
    create_empty_database(DB_A)
    with pytest.raises(DatabaseExists):
        create_empty_database(DB_A)


def test_drop_absent_returns_false():
    assert drop_database('company_absent_db') is False


def test_kill_connections_best_effort():
    # Sin conexiones ajenas a la base recién creada, no rompe.
    create_empty_database(DB_A)
    kill_connections(DB_A)  # no debe lanzar
    drop_database(DB_A)


def test_duplicate_copies_schema_and_data():
    # PostgreSQL NO permite calificar una tabla con el nombre de la base
    # (``base.tabla`` designa ``schema.tabla``): hay que CONECTARSE a cada base.
    # Bajo MariaDB el ``\`db\`.tabla`` funcionaba porque allá base y schema son
    # lo mismo. Se usa el mismo helper que ``service.db`` (``_connect``).
    create_empty_database(DB_A)
    with closing_cursor(_connect(DB_A)) as c:
        c.execute('CREATE TABLE widget (id INT PRIMARY KEY, name VARCHAR(20))')
        c.execute("INSERT INTO widget VALUES (1, 'uno')")
    duplicate_database(DB_A, DB_B)
    assert database_exists(DB_B) is True
    with closing_cursor(_connect(DB_B)) as c:
        c.execute('SELECT id, name FROM widget')
        assert list(c.fetchall()) == [(1, 'uno')]


def test_rename_moves_database():
    create_empty_database(DB_A)
    with closing_cursor(_connect(DB_A)) as c:
        c.execute('CREATE TABLE widget (id INT PRIMARY KEY)')
    rename_database(DB_A, DB_B)
    assert database_exists(DB_A) is False
    assert database_exists(DB_B) is True


def test_create_database_respects_management_guard():
    # == exp_create_database bajo check_db_management_enabled: con la gestión
    # deshabilitada, create_database NO crea nada.
    # (El paso de inicialización = ``migrate --database`` es Django-nativo y se
    # ejerce en runtime con el alias cableado, T-091-05; aquí sólo el guard.)
    with override_settings(MULTIDB_MANAGEMENT_ENABLED=False):
        with pytest.raises(DatabaseManagementDisabled):
            create_database(DB_C)
    assert database_exists(DB_C) is False


def test_db_monodb_single_match():
    create_empty_database(DB_C)
    with override_settings(MULTIDB_DBFILTER=r'^company_9003_db$'):
        assert db_monodb('9003.kaupamex.mx') == DB_C
    drop_database(DB_C)
