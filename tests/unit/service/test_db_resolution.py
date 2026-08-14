"""Contract for the dynamic DATABASES loader (SOL-091, T-091-04).

Compone las entradas ``company_<N>_db`` de ``DATABASES`` clonando ``default`` y
cambiando **sólo** ``NAME`` (F-DJ-02: ``ConnectionHandler`` construye una
conexión por alias al primer uso; cada entrada debe ser un dict completo).
Función pura — sin DB ni I/O.
"""
from service.db import (
    build_company_alias,
    build_company_databases,
    db_filter,
    filter_company_dbs,
)

BASE = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'kaupamex_core_qa',
    'USER': 'django_user',
    'PASSWORD': 'secret',
    'HOST': '127.0.0.1',
    'PORT': '3306',
    'OPTIONS': {'unix_socket': '/run/mysqld/mysqld.sock'},
}


def test_clone_changes_only_name():
    entry = build_company_alias(BASE, 'company_1_db')
    assert entry['NAME'] == 'company_1_db'
    assert entry['USER'] == 'django_user'
    assert entry['OPTIONS'] == {'unix_socket': '/run/mysqld/mysqld.sock'}


def test_clone_is_deep_copy():
    entry = build_company_alias(BASE, 'company_1_db')
    entry['OPTIONS']['unix_socket'] = '/tmp/other.sock'
    # mutar el clon no toca el template 'default'
    assert BASE['OPTIONS']['unix_socket'] == '/run/mysqld/mysqld.sock'


def test_build_maps_each_db_name_to_its_own_alias():
    dbs = build_company_databases(['company_1_db', 'company_2_db'], BASE)
    assert set(dbs) == {'company_1_db', 'company_2_db'}
    assert dbs['company_1_db']['NAME'] == 'company_1_db'
    assert dbs['company_2_db']['NAME'] == 'company_2_db'


def test_build_empty_for_n1():
    # N=1: sin bases por empresa -> DATABASES sólo tendrá 'default'.
    assert build_company_databases([], BASE) == {}


def test_filter_keeps_only_company_db_shape():
    # == db_filter de Odoo: descarta schemas del sistema y de negocio L0,
    # queda sólo company_<N>_db. Preserva el orden de entrada.
    raw = [
        'company_2_db', 'information_schema', 'kaupamex_core', 'company_10_db',
        'mysql', 'company_db', 'companyx_db', 'performance_schema',
    ]
    assert filter_company_dbs(raw) == ['company_2_db', 'company_10_db']


def test_filter_empty_when_no_company_dbs():
    assert filter_company_dbs(['mysql', 'kaupamex_core']) == []


# --- db_filter: adaptación fiel de Odoo http.py:389-425 (host->db) ---

DBS = ['company_2_db', 'company_5_db', 'company_10_db']


def test_db_filter_matches_subdomain_via_percent_d():
    # dbfilter '^company_%d_db$' + host '5.kaupamex.mx' -> domain '5' ->
    # regex '^company_5_db$' -> matchea company_5_db.
    assert db_filter(DBS, '5.kaupamex.mx', dbfilter=r'^company_%d_db$') == ['company_5_db']


def test_db_filter_strips_www_and_port():
    # 'www.10.kaupamex.mx:8000' -> quita puerto y www -> '10.kaupamex.mx' ->
    # domain '10' -> company_10_db.
    got = db_filter(DBS, 'www.10.kaupamex.mx:8000', dbfilter=r'^company_%d_db$')
    assert got == ['company_10_db']


def test_db_filter_percent_h_uses_full_host():
    # %h = host completo (sin puerto/www). Con host '2' el regex '^company_%h_db$'
    # da '^company_2_db$'.
    assert db_filter(DBS, '2', dbfilter=r'^company_%h_db$') == ['company_2_db']


def test_db_filter_whitelist_when_no_dbfilter():
    # Sin dbfilter, con db_name (lista blanca == --database): intersección ordenada.
    assert db_filter(DBS, 'x', dbfilter='', db_name=['company_5_db', 'company_2_db']) \
        == ['company_2_db', 'company_5_db']


def test_db_filter_passthrough_without_config():
    # Sin dbfilter ni whitelist: devuelve la lista tal cual.
    assert db_filter(DBS, 'x', dbfilter='', db_name=None) == DBS


def test_db_filter_no_match_returns_empty():
    assert db_filter(DBS, '99.kaupamex.mx', dbfilter=r'^company_%d_db$') == []
