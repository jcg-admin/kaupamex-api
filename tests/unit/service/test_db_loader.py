"""Unit tests del loader de aliases multi-DB (SOL-091, T-091-05).

``install_company_aliases`` puebla el dict ``DATABASES`` con un alias por base
``company_<N>_db`` (== ``connection_info_for`` de cada base al boot). Con roster
explícito no consulta la DB (12-factor, safe en import); con ``names=None``
descubre por ``information_schema`` (uso runtime). Lógica pura salvo la rama de
descubrimiento (mockeada).
"""
from unittest import mock

from service.db import install_company_aliases


def _base_databases():
    return {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'kaupamex_core',
            'USER': 'django_user',
            'OPTIONS': {'unix_socket': '/run/mysqld/mysqld.sock'},
        }
    }


def test_loader_populates_one_alias_per_company_db():
    dbs = _base_databases()
    install_company_aliases(dbs, ['company_1_db', 'company_2_db'])
    assert set(dbs) == {'default', 'company_1_db', 'company_2_db'}
    assert dbs['company_1_db']['NAME'] == 'company_1_db'
    assert dbs['company_2_db']['NAME'] == 'company_2_db'
    # Hereda ENGINE/USER/OPTIONS del default.
    assert dbs['company_1_db']['ENGINE'] == 'django.db.backends.mysql'
    assert dbs['company_1_db']['USER'] == 'django_user'


def test_loader_deep_copies_options_independent_from_default():
    dbs = _base_databases()
    install_company_aliases(dbs, ['company_1_db'])
    # Mutar el OPTIONS del alias NO debe tocar el del default (F-DJ-02).
    dbs['company_1_db']['OPTIONS']['unix_socket'] = '/other.sock'
    assert dbs['default']['OPTIONS']['unix_socket'] == '/run/mysqld/mysqld.sock'


def test_loader_empty_roster_is_noop_n1():
    dbs = _base_databases()
    install_company_aliases(dbs, [])
    assert list(dbs) == ['default']


def test_loader_is_idempotent():
    dbs = _base_databases()
    install_company_aliases(dbs, ['company_1_db'])
    dbs['company_1_db']['NAME'] = 'company_1_db'  # ya presente
    install_company_aliases(dbs, ['company_1_db'])  # segunda pasada
    assert list(dbs) == ['default', 'company_1_db']


@mock.patch('service.db.list_company_db_names')
def test_loader_names_none_discovers_from_information_schema(mock_list):
    mock_list.return_value = ['company_7_db']
    dbs = _base_databases()
    install_company_aliases(dbs)  # names=None → descubre
    mock_list.assert_called_once()
    assert set(dbs) == {'default', 'company_7_db'}
