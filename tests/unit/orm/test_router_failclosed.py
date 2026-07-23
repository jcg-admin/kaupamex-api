"""Fail-closed duro del router bajo N>1 (SOL-091, T-091-05 — el guard del wiring).

El router (``test_multidb_router``) devuelve ``None`` para dominio sin empresa
activa → Django cae a ``default``. Correcto para **N=1** (el dominio vive en
``default``). Pero bajo **N>1** (hay bases ``company_<N>_db`` configuradas) esa
caída **filtraría** dominio de una empresa a ``default``: el guard convierte ese
``None`` en un rechazo duro (``CompanyContextRequired``). La activación es
automática — se basa en si ``settings.DATABASES`` tiene aliases ``company_*``.
"""
from django.test import override_settings

from addons.company.context import company_scope, set_current_company
from orm.routers import CompanyDatabaseRouter, CompanyContextRequired
import pytest


class _Meta:
    def __init__(self, app_label, model_name):
        self.app_label = app_label
        self.model_name = model_name


class _Model:
    def __init__(self, app_label, model_name='thing'):
        self._meta = _Meta(app_label, model_name)


DOMAIN = _Model('catalogue', 'product')
SESSION = _Model('sessions', 'session')
router = CompanyDatabaseRouter()

_N_GT_1 = {
    'default': {'ENGINE': 'django.db.backends.mysql', 'NAME': 'kaupamex_db'},
    'company_5_db': {'ENGINE': 'django.db.backends.mysql', 'NAME': 'company_5_db'},
}


@override_settings(DATABASES=_N_GT_1)
def test_domain_without_company_under_n_gt_1_raises():
    set_current_company(None)
    with pytest.raises(CompanyContextRequired):
        router.db_for_read(DOMAIN)
    with pytest.raises(CompanyContextRequired):
        router.db_for_write(DOMAIN)


@override_settings(DATABASES=_N_GT_1)
def test_control_plane_under_n_gt_1_still_goes_to_default():
    set_current_company(None)
    assert router.db_for_read(SESSION) == 'default'
    assert router.db_for_write(SESSION) == 'default'


@override_settings(DATABASES=_N_GT_1)
def test_domain_with_active_company_routes_to_its_db_under_n_gt_1():
    with company_scope(5):
        assert router.db_for_write(DOMAIN) == 'company_5_db'


@override_settings(DATABASES=_N_GT_1)
def test_domain_with_unprovisioned_company_under_n_gt_1_raises():
    # Empresa activa cuya base NO está configurada, en modo multi-DB: no puede
    # caer a 'default' (filtraría) -> fail-closed (H-API-091-06).
    with company_scope(99):  # company_99_db no está en _N_GT_1
        with pytest.raises(CompanyContextRequired):
            router.db_for_write(DOMAIN)


def test_n1_neutrality_domain_without_company_returns_none():
    # Sin aliases company en settings (N=1, settings de testing): NO rechaza,
    # cae a default (None) — preserva el contrato existente.
    set_current_company(None)
    assert router.db_for_read(DOMAIN) is None
    assert router.db_for_write(DOMAIN) is None
