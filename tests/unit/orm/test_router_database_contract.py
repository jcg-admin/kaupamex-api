"""DEC-AISL-05: el roster y la base ligada gobiernan el aislamiento."""
from types import SimpleNamespace

from django.test import override_settings
import pytest

from orm.environments import company_scope
from orm.routers import CompanyDatabaseRouter

pytestmark = pytest.mark.filterwarnings('ignore:Overriding setting DATABASES:UserWarning')
DATABASES = {
    'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'control'},
    'company_5_db': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'tenant'},
    'company_not_a_number_db': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'invalid'},
}


def model(app, database=None):
    return SimpleNamespace(_meta=SimpleNamespace(app_label=app, model_name='thing'),
                           _state=SimpleNamespace(db=database))


@override_settings(DATABASES=DATABASES)
@pytest.mark.parametrize('app', ['base', 'base_address_extended', 'base_geolocalize'])
def test_base_addons_route_to_the_selected_company(app):
    with company_scope(5):
        router = CompanyDatabaseRouter()
        assert router.db_for_read(model(app)) == 'company_5_db'
        assert router.db_for_write(model(app)) == 'company_5_db'
        assert router.allow_migrate('company_5_db', app, 'thing') is True


@override_settings(DATABASES=DATABASES)
@pytest.mark.parametrize('alias', ['company_9_db', 'company_not_a_number_db', 'company_', 'other'])
def test_migrations_reject_unknown_or_invalid_company_aliases(alias):
    assert CompanyDatabaseRouter().allow_migrate(alias, 'product', 'thing') is False


@override_settings(DATABASES=DATABASES)
def test_bound_objects_from_different_databases_cannot_relate_under_one_context():
    with company_scope(5):
        assert CompanyDatabaseRouter().allow_relation(model('base', 'default'),
                                                       model('base', 'company_5_db')) is False


@override_settings(DATABASES=DATABASES)
def test_bound_objects_keep_their_own_database_when_context_changes():
    with company_scope(5):
        assert CompanyDatabaseRouter().allow_relation(model('base', 'default'),
                                                       model('base', 'default')) is True
