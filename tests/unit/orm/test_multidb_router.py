"""Contract for CompanyDatabaseRouter (SOL-091, Palanca B, DB-per-company).

Adaptación fiel de Odoo 19 (F-ODOO-06, analisis-adaptacion-odoo-multidb): la
Registry hace ``self._db = sql_db.db_connect(db_name)`` y ``cursor(readonly)``
separa primaria/réplica (orm/registry.py:244-249, 1165-1186). En Django la
conexión por base es ``connections[alias]`` y ese split lectura/escritura son
``db_for_read``/``db_for_write``. Lógica pura del router — sin DB.

El plano de control (lo que vive en ``default``) es infraestructura de Django
(``sessions``, ``contenttypes``), no un modelo aplicativo: ``orm`` no registra
ninguna entidad. La lista de bases de empresa se descubre de
``information_schema`` (== ``list_dbs`` de Odoo), no de una tabla.
"""
from django.test import override_settings

from orm.environments import company_scope, set_current_company
from orm.routers import CompanyDatabaseRouter, company_db_alias

# Routing DB-per-company (N>1) sólo activa cuando la base de la empresa está
# configurada en ``settings.DATABASES``. Bajo N=1 (settings de testing, sin
# aliases company) el router degenera a ``default`` aunque haya empresa activa,
# para no romper el row-scoping SOL-085 (H-API-091-06). Los tests que verifican
# el ruteo a ``company_5_db`` configuran ese alias explícitamente.
_WITH_COMPANY_5 = {
    'default': {'ENGINE': 'django.db.backends.mysql', 'NAME': 'kaupamex_db'},
    'company_5_db': {'ENGINE': 'django.db.backends.mysql', 'NAME': 'company_5_db'},
}


class _Meta:
    def __init__(self, app_label, model_name):
        self.app_label = app_label
        self.model_name = model_name


class _Model:
    """Modelo falso: el router sólo lee ``_meta.app_label`` / ``model_name``."""

    def __init__(self, app_label, model_name='thing'):
        self._meta = _Meta(app_label, model_name)


DOMAIN = _Model('catalogue', 'product')
SESSION = _Model('sessions', 'session')       # plano de control (infra Django)
CONTENTTYPE = _Model('contenttypes', 'contenttype')

router = CompanyDatabaseRouter()


def test_company_db_alias_maps_id_to_alias():
    assert company_db_alias(5) == 'company_5_db'
    assert company_db_alias(None) is None


@override_settings(DATABASES=_WITH_COMPANY_5)
def test_domain_reads_and_writes_go_to_active_company_db():
    # Con la base de la empresa provisionada (N>1) el dominio rutea a su base.
    with company_scope(5):
        assert router.db_for_read(DOMAIN) == 'company_5_db'
        assert router.db_for_write(DOMAIN) == 'company_5_db'


def test_domain_without_active_company_returns_none_n1():
    # N=1 (settings de testing, sin aliases company): sin empresa -> default.
    set_current_company(None)
    assert router.db_for_read(DOMAIN) is None
    assert router.db_for_write(DOMAIN) is None


def test_domain_with_active_company_but_unprovisioned_db_degenerates_n1():
    # N=1 + empresa activa cuya base NO está provisionada: degenera a 'default'
    # (None) para que el row-scoping SOL-085 aísle por columna (H-API-091-06).
    with company_scope(5):  # company_5_db NO está en settings de testing
        assert router.db_for_read(DOMAIN) is None
        assert router.db_for_write(DOMAIN) is None


def test_control_plane_infra_goes_to_default():
    with company_scope(5):
        assert router.db_for_read(SESSION) == 'default'
        assert router.db_for_write(CONTENTTYPE) == 'default'


def test_allow_migrate_keeps_control_plane_only_in_default():
    assert router.allow_migrate('default', 'sessions', 'session') is True
    assert router.allow_migrate('company_5_db', 'sessions', 'session') is False
    assert router.allow_migrate('default', 'contenttypes', 'contenttype') is True
    assert router.allow_migrate('company_5_db', 'contenttypes', 'contenttype') is False


def test_allow_migrate_domain_in_company_db_and_default_for_n1():
    assert router.allow_migrate('company_5_db', 'catalogue', 'product') is True
    # Degeneración N=1: el dominio también puede vivir en 'default'.
    assert router.allow_migrate('default', 'catalogue', 'product') is True


@override_settings(DATABASES=_WITH_COMPANY_5)
def test_allow_relation_only_within_same_alias():
    with company_scope(5):
        assert router.allow_relation(DOMAIN, _Model('orders', 'order')) is True
        # dominio (company_5_db) vs infra de control (default) -> distinto alias.
        assert router.allow_relation(DOMAIN, SESSION) is False
