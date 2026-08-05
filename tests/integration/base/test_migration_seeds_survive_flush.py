"""Tests — H-API-22: las semillas de data-migration sobreviven a un flush.

**El defecto.** Un test ``django_db(transaction=True)`` es un
``TransactionTestCase``: Django hace ``flush`` de todas las tablas de modelos en
su teardown. ``django_migrations`` no es tabla de modelo, así que sobrevive — la
data-migration queda registrada como aplicada sobre una tabla vacía y **nunca
vuelve a correr**. Todo test posterior de la sesión ve las semillas ausentes, y
el fallo aparece lejos de la causa (``get_param`` que devuelve ``None``, un
subtipo de mensaje que no existe).

Medido el 2026-07-28 en ``kaupamex_qa``: tras re-aplicar las cuatro migraciones
de semilla (``system_parameter``=3, ``mail_message_subtype``=2,
``base_geo_provider``=2), **un solo** test transaccional dejó las tres en 0.

**La corrección.** Cada addon expone ``data.seed()`` idempotente — el
equivalente nativo del ``data/*.xml`` que Odoo re-aplica al actualizar el
módulo — y el fixture ``restore_migration_seeds`` del conftest lo re-aplica tras
un test transaccional. Estos tests fijan las dos mitades del contrato:

1. ``seed()`` es idempotente (llamarlo dos veces no duplica).
2. Un test transaccional **no** deja sin semillas al siguiente — el orden de
   ejecución deja de importar.

El test 2 depende del orden dentro de esta clase (``-p no:randomly`` está en
``pytest.ini``): el transaccional corre antes que el que verifica.
"""
import pytest
from django.test import override_settings

from addons.authz_password_policy.data import PASSWORD_POLICY_PARAMETERS
from addons.authz_password_policy.data import seed as password_policy_seed
from addons.authz_signup.data import SIGNUP_PARAMETERS
from addons.authz_signup.data import seed as signup_flags_seed
from addons.authz_totp.data import TOTP_PARAMETERS
from addons.authz_totp.data import seed as totp_params_seed
from addons.base.models import SystemParameter
from addons.base_geolocalize.data import GEO_PROVIDERS
from addons.base_geolocalize.data import seed as geo_providers_seed
from addons.base_geolocalize.models import GeoProvider
from addons.sale_subscription.data.res_company_data import (
    seed as bootstrap_company_seed,
)
from addons.base.models import ResCompany
from addons.mail.data import CANONICAL_SUBTYPES
from addons.mail.data import seed as mail_subtypes_seed
from addons.mail.models import MailMessageSubtype

import tests.conftest as conftest

pytestmark = pytest.mark.django_db

_SEED_KEYS = (tuple(PASSWORD_POLICY_PARAMETERS) + tuple(SIGNUP_PARAMETERS)
              + tuple(TOTP_PARAMETERS))

_ALL_SEEDERS = (password_policy_seed, signup_flags_seed, totp_params_seed,
                mail_subtypes_seed, geo_providers_seed, bootstrap_company_seed)

# La empresa de bootstrap NO entra en ``_seeds_present``: su semilla depende de
# ``BOOTSTRAP_COMPANY_CODE`` (DEC-3 — la app ya no nombra ninguna empresa L1 en
# código), y en la suite esa clave está vacía, así que ``seed()`` es un no-op
# legítimo. Su restauración se verifica aparte, declarando el código con
# ``override_settings`` (``TestRestauracionDeLaEmpresaDeBootstrap``).
_BOOTSTRAP_CODE = 'bootstrap-flush-test'


def _seeds_present():
    """Estado de todas las familias de semilla, como dict verificable."""
    return {
        'params': SystemParameter.objects.filter(key__in=_SEED_KEYS).count(),
        'subtypes': MailMessageSubtype.objects.filter(
            name__in=[s['name'] for s in CANONICAL_SUBTYPES],
            res_model='').count(),
        'geo': GeoProvider.objects.filter(
            tech_name__in=[t for t, _ in GEO_PROVIDERS]).count(),
    }


_ESPERADO = {
    'params': len(_SEED_KEYS),
    'subtypes': len(CANONICAL_SUBTYPES),
    'geo': len(GEO_PROVIDERS),
}


class TestSeedEsIdempotente:
    """``seed()`` se puede llamar N veces: crea lo ausente, no duplica."""

    def test_doble_llamada_no_duplica(self):
        for seed in _ALL_SEEDERS:
            seed()
            seed()
        assert _seeds_present() == _ESPERADO

    def test_seed_no_pisa_un_valor_editado(self):
        """L2 es editable en caliente: ``seed()`` no revierte la edición."""
        key = next(iter(PASSWORD_POLICY_PARAMETERS))
        password_policy_seed()
        SystemParameter.set_param(key, '12')
        password_policy_seed()
        assert SystemParameter.get_param(key) == '12'


class TestRestauracionTrasElFlush:
    """El núcleo de H-API-22: lo borrado se restaura.

    **Por qué no se testea con "un transaccional y luego otro test".** El
    intento natural —marcar un test ``transaction=True`` y verificar en el
    siguiente— es imposible: **pytest-django reordena** y corre los tests
    transaccionales al **final** de su grupo, así que ningún test del archivo
    puede quedar después. Verificado con ``-v``: el test no transaccional
    reportó 75% y el transaccional 100%, en contra del orden de definición.

    Ese reordenamiento explica además la **forma real** del defecto: el flush
    cae al cierre de la sesión, así que el daño no se ve en la corrida que lo
    causa — se ve en la **siguiente**, que con ``--reuse-db`` arranca sobre una
    BD ya vacía. Por eso las semillas "aplicadas" llevaban tanto tiempo en cero.

    Se verifica entonces el contrato que el hook usa: borrar todo y re-sembrar
    devuelve exactamente el estado de las migraciones.
    """

    def test_borrar_y_re_sembrar_restaura_el_estado_de_migracion(self):
        SystemParameter.objects.filter(key__in=_SEED_KEYS).delete()
        MailMessageSubtype.objects.filter(res_model='').delete()
        GeoProvider.objects.all().delete()
        assert _seeds_present() != _ESPERADO      # el flush deja hueco real

        for seed in _ALL_SEEDERS:                 # lo que corre el hook
            seed()
        assert _seeds_present() == _ESPERADO

    def test_el_hook_de_teardown_esta_cableado(self):
        """Sin el hook la restauración no ocurre — se fija que exista.

        El hook es la única pieza que corre **después** del ``flush``: los
        finalizadores de fixture no pueden (``db`` se instala antes que los
        autouse del conftest, así que se finaliza después de ellos).
        """
        assert hasattr(conftest, 'pytest_runtest_teardown')
        assert set(conftest._SEEDERS) >= set(_ALL_SEEDERS)


class TestRestauracionDeLaEmpresaDeBootstrap:
    """La empresa declarada en config también se restaura tras el flush.

    Va aparte porque su semilla es condicional: sin ``BOOTSTRAP_COMPANY_CODE``
    no hay empresa que sembrar (DEC-3), así que el código se declara aquí con
    ``override_settings`` en vez de asumirlo en ``_ESPERADO``.
    """

    def test_borrar_y_re_sembrar_restaura_la_empresa_declarada(self):
        with override_settings(BOOTSTRAP_COMPANY_CODE=_BOOTSTRAP_CODE,
                               BOOTSTRAP_COMPANY_NAME='Bootstrap Flush Test'):
            bootstrap_company_seed()
            assert ResCompany.objects.filter(code=_BOOTSTRAP_CODE).exists()

            ResCompany.objects.filter(code=_BOOTSTRAP_CODE).delete()
            assert not ResCompany.objects.filter(code=_BOOTSTRAP_CODE).exists()

            bootstrap_company_seed()              # lo que corre el hook
            assert ResCompany.objects.filter(code=_BOOTSTRAP_CODE).count() == 1

    def test_sin_codigo_declarado_el_sembrador_no_fabrica_empresas(self):
        with override_settings(BOOTSTRAP_COMPANY_CODE=''):
            antes = ResCompany.objects.count()
            assert bootstrap_company_seed() is None
            assert ResCompany.objects.count() == antes
