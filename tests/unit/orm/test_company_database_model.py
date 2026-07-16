"""Contract for the L0 registry model CompanyDatabase (SOL-091, T-091-02).

El registro L0 (equivalente al listado de bases de Odoo, service/db.list_dbs ->
pg_database) vive en 'default'; el loader de DATABASES (T-091-04) lo lee para
componer las conexiones company_<N>_db. NO es Company/res.company (que vive
por-base). Ver at-aislamiento-multi-db-per-company (D-091-1).
"""
import pytest

from orm.models import CompanyDatabase

pytestmark = pytest.mark.django_db


def test_registry_row_defaults_to_trial():
    row = CompanyDatabase.objects.create(code='acme', db_name='company_1_db')
    assert row.status == CompanyDatabase.STATUS_TRIAL
    assert CompanyDatabase.objects.get(code='acme').db_name == 'company_1_db'


def test_code_is_unique():
    CompanyDatabase.objects.create(code='acme', db_name='company_1_db')
    with pytest.raises(Exception):
        CompanyDatabase.objects.create(code='acme', db_name='company_2_db')


def test_is_provisionable_only_for_active_and_trial():
    active = CompanyDatabase.objects.create(
        code='a', db_name='company_a_db', status=CompanyDatabase.STATUS_ACTIVE)
    trial = CompanyDatabase.objects.create(
        code='t', db_name='company_t_db', status=CompanyDatabase.STATUS_TRIAL)
    susp = CompanyDatabase.objects.create(
        code='s', db_name='company_s_db', status=CompanyDatabase.STATUS_SUSPENDED)
    assert active.is_provisionable is True
    assert trial.is_provisionable is True
    assert susp.is_provisionable is False
