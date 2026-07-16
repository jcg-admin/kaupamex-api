"""Contract for CompanyDatabaseRouter (SOL-091, Palanca B, DB-per-company).

Adaptación fiel de Odoo 19 (F-ODOO-06, analisis-adaptacion-odoo-multidb): la
Registry hace ``self._db = sql_db.db_connect(db_name)`` y ``cursor(readonly)``
separa primaria/réplica (orm/registry.py:244-249, 1165-1186). En Django la
conexión por base es ``connections[alias]`` y ese split lectura/escritura son
``db_for_read``/``db_for_write``. Lógica pura del router — sin DB.
"""
from apps.platform.company.context import company_scope, set_current_company
from apps.platform.orm.routers import CompanyDatabaseRouter, company_db_alias


class _Meta:
    def __init__(self, app_label, model_name):
        self.app_label = app_label
        self.model_name = model_name


class _Model:
    """Modelo falso: el router sólo lee ``_meta.app_label`` / ``model_name``."""

    def __init__(self, app_label, model_name='thing'):
        self._meta = _Meta(app_label, model_name)


DOMAIN = _Model('catalogue', 'product')
REGISTRY = _Model('orm', 'companydatabase')   # plano de control L0 (app orm)
SESSION = _Model('sessions', 'session')

router = CompanyDatabaseRouter()


def test_company_db_alias_maps_id_to_alias():
    assert company_db_alias(5) == 'company_5_db'
    assert company_db_alias(None) is None


def test_domain_reads_and_writes_go_to_active_company_db():
    with company_scope(5):
        assert router.db_for_read(DOMAIN) == 'company_5_db'
        assert router.db_for_write(DOMAIN) == 'company_5_db'


def test_domain_is_fail_closed_without_active_company():
    set_current_company(None)
    assert router.db_for_read(DOMAIN) is None
    assert router.db_for_write(DOMAIN) is None


def test_control_plane_registry_and_session_go_to_default():
    with company_scope(5):
        assert router.db_for_read(REGISTRY) == 'default'
        assert router.db_for_write(SESSION) == 'default'


def test_allow_migrate_keeps_control_plane_only_in_default():
    assert router.allow_migrate('default', 'orm', 'companydatabase') is True
    assert router.allow_migrate('company_5_db', 'orm', 'companydatabase') is False
    assert router.allow_migrate('default', 'sessions', 'session') is True
    assert router.allow_migrate('company_5_db', 'sessions', 'session') is False


def test_allow_migrate_domain_in_company_db_and_default_for_n1():
    assert router.allow_migrate('company_5_db', 'catalogue', 'product') is True
    # Degeneración N=1: el dominio también puede vivir en 'default'.
    assert router.allow_migrate('default', 'catalogue', 'product') is True


def test_allow_relation_only_within_same_alias():
    with company_scope(5):
        assert router.allow_relation(DOMAIN, _Model('orders', 'order')) is True
        # dominio (company_5_db) vs registro L0 (default) -> distinto alias.
        assert router.allow_relation(DOMAIN, REGISTRY) is False
