"""Contrato de ``_reauth_ttl`` tras migrar a SystemParameter L2 (slice 2 de
``implementar-systemparameter-l2``; cierra H-API-CFG-02,
:ref:`hallazgos-estrategia-configuracion-kaupamex`).

Antes leía ``settings.AUTHZ_REAUTH_TTL`` (``default=`` cableado en código);
ahora lee ``SystemParameter.get_param('authz.reauth_ttl')``, editable en
caliente y sembrado por la migración de datos de ``addons.base``.
"""
import pytest

from addons.authz.services import _reauth_ttl
from addons.base.models import SystemParameter
from orm.registry import clear_cache

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_param_cache(db):
    """La caché de SystemParameter es módulo-nivel (per-proceso), no
    per-transacción; se limpia entre tests para aislarlos.

    Además reseed idempotente: un test ``transaction=True`` previo (aislamiento
    multi-DB SOL-091) hace ``flush`` de ``system_parameter`` sin re-correr la
    data-migration, así que ``test_lee_el_default_sembrado`` sería
    order-dependent sin restaurar la fila sembrada."""
    clear_cache('stable')
    SystemParameter.seed()
    yield
    clear_cache('stable')


class TestReauthTtl:
    def test_lee_el_default_sembrado_por_la_migracion(self):
        # 0003_seed_business_keys siembra 'authz.reauth_ttl' = '900'
        # (equivalente al viejo AUTHZ_REAUTH_TTL default=900).
        assert _reauth_ttl() == 900
        assert SystemParameter.get_param('authz.reauth_ttl') == '900'

    def test_honra_el_valor_sobreescrito_via_set_param(self):
        SystemParameter.set_param('authz.reauth_ttl', '120')
        assert _reauth_ttl() == 120

    def test_devuelve_int_no_str(self):
        SystemParameter.set_param('authz.reauth_ttl', '300')
        ttl = _reauth_ttl()
        assert isinstance(ttl, int)
        assert ttl == 300

    def test_valor_vacio_cae_al_default_del_llamado(self):
        # 'authz.reauth_ttl' está en _DEFAULT_PARAMETERS -> protegida contra
        # borrado/renombrado (H-CFG-IMPL-01); no se puede simular "ausente"
        # con delete. Un valor vacío sí es editable y activa el quirk
        # ``or default`` (H-CFG-IMPL-03): cae al default explícito de
        # _reauth_ttl (900), no a un default de settings.
        SystemParameter.set_param('authz.reauth_ttl', '')
        assert _reauth_ttl() == 900
