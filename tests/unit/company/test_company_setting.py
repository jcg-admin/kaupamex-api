"""Contrato de ``CompanySetting`` (L3 per-empresa) — SOL-090 slice 3.

Diseño: :ref:`analisis-estrategia-configuracion-capas` (capa L3, sección 7).
Cierra :ref:`hallazgos-implementar-systemparameter-l2` (H-CFG-IMPL-10).

Extiende el patrón L2 de ``addons.base.SystemParameter`` (key/value) a la
dimensión per-empresa: FK ``company`` + ``RuleScopedManager`` (SOL-085),
igual que ``CompanyModuleSubscription``. A diferencia de L2 (plano de
control, ``get_param``/``set_param`` sin dimensión de empresa),
``get_setting``/``set_setting`` resuelven la empresa (parámetro explícito o
contexto ambiente) y caen a ``default`` sin excepción cuando no hay empresa
o no hay fila — comportamiento legítimo mientras no exista el resolutor
subdominio→company (UC-PLT-06), no un error.
"""
import pytest
from django.db import IntegrityError, transaction

from orm.environments import company_scope, get_current_company
from addons.base.models import CompanySetting
from addons.sale_subscription.data.res_company_data import (
    FOUNDER_COMPANY_CODE,
    FOUNDER_L1_SETTINGS,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


def _company(code):
    return ResCompany.objects.create(code=code, name=code)


class TestGetSettingFallback:
    def test_no_company_param_no_ambient_context_returns_default(self):
        assert get_current_company() is None
        assert CompanySetting.get_setting('contact.from_email') is None
        assert CompanySetting.get_setting(
            'contact.from_email', 'hola@kaupamex.com',
        ) == 'hola@kaupamex.com'

    def test_company_with_no_row_returns_default(self):
        acme = _company('acme-setting-1')
        value = CompanySetting.get_setting(
            'contact.from_email', 'hola@kaupamex.com', company=acme,
        )
        assert value == 'hola@kaupamex.com'


class TestSetAndGetSetting:
    def test_set_then_get_by_company_instance(self):
        acme = _company('acme-setting-2')
        CompanySetting.set_setting('contact.from_email', 'hola@acme.com', acme)
        assert CompanySetting.get_setting(
            'contact.from_email', company=acme,
        ) == 'hola@acme.com'

    def test_set_then_get_by_company_id(self):
        acme = _company('acme-setting-3')
        CompanySetting.set_setting('contact.from_email', 'hola@acme.com', acme.pk)
        assert CompanySetting.get_setting(
            'contact.from_email', company=acme.pk,
        ) == 'hola@acme.com'

    def test_get_uses_ambient_company_scope_when_no_company_param(self):
        acme = _company('acme-setting-4')
        CompanySetting.set_setting('contact.from_email', 'hola@acme.com', acme)
        with company_scope(acme.pk):
            assert CompanySetting.get_setting('contact.from_email') == 'hola@acme.com'
        # fuera del scope, sin company param -> default (no hay empresa ambiente)
        assert CompanySetting.get_setting(
            'contact.from_email', 'fallback@kaupamex.com',
        ) == 'fallback@kaupamex.com'

    def test_set_updates_existing_value(self):
        acme = _company('acme-setting-5')
        CompanySetting.set_setting('contact.from_email', 'v1@acme.com', acme)
        CompanySetting.set_setting('contact.from_email', 'v2@acme.com', acme)
        assert CompanySetting.get_setting(
            'contact.from_email', company=acme,
        ) == 'v2@acme.com'
        assert CompanySetting.objects.filter(
            company=acme, key='contact.from_email',
        ).count() == 1

    def test_set_without_resolvable_company_raises(self):
        assert get_current_company() is None
        with pytest.raises(ValueError):
            CompanySetting.set_setting('contact.from_email', 'x@x.com', None)


class TestPerCompanyIsolation:
    def test_two_companies_have_independent_values_for_same_key(self):
        acme = _company('acme-setting-6')
        globex = _company('globex-setting-6')
        CompanySetting.set_setting('contact.from_email', 'hola@acme.com', acme)
        CompanySetting.set_setting('contact.from_email', 'hola@globex.com', globex)
        assert CompanySetting.get_setting(
            'contact.from_email', company=acme,
        ) == 'hola@acme.com'
        assert CompanySetting.get_setting(
            'contact.from_email', company=globex,
        ) == 'hola@globex.com'

    def test_scoped_manager_fail_closed_without_ambient_company(self):
        acme = _company('acme-setting-7')
        CompanySetting.set_setting('contact.from_email', 'hola@acme.com', acme)
        assert get_current_company() is None
        assert CompanySetting.scoped.for_current_company().count() == 0

    def test_scoped_manager_scopes_rows_under_ambient_company(self):
        acme = _company('acme-setting-8')
        globex = _company('globex-setting-8')
        CompanySetting.set_setting('contact.from_email', 'hola@acme.com', acme)
        CompanySetting.set_setting('contact.from_email', 'hola@globex.com', globex)
        with company_scope(acme.pk):
            rows = CompanySetting.scoped.for_current_company()
            assert {r.company_id for r in rows} == {acme.pk}

    def test_default_manager_sees_all_companies(self):
        acme = _company('acme-setting-9')
        globex = _company('globex-setting-9')
        CompanySetting.set_setting('contact.from_email', 'hola@acme.com', acme)
        CompanySetting.set_setting('contact.from_email', 'hola@globex.com', globex)
        assert CompanySetting.objects.filter(
            key='contact.from_email',
            company__in=[acme, globex],
        ).count() == 2


class TestFounderSeeding:
    """Migración ``company/0006_seed_founder_settings`` — PracticaYoruba es
    un tenant **L1** (founder, NO L0/Kaupamex): sus valores de contacto/
    newsletter no eran stale, se siembran como SU propio ``CompanySetting``.
    """

    @pytest.fixture(autouse=True)
    def _reseed_founder_settings(self, db):
        # Reseed idempotente: un test ``transaction=True`` previo (p.ej. el
        # de aislamiento multi-DB SOL-091,
        # tests/integration/platform/test_multidb_isolation.py) hace
        # ``flush`` de 'default' sin re-correr la data-migration
        # company/0006_seed_founder_settings, dejando ausente la fila
        # founder + sus CompanySetting para los tests que corren después —
        # mismo patrón order-dependent que H-CFG-IMPL-09 (SystemParameter,
        # tests/unit/base/test_system_parameter.py). Restaura el estado que
        # la migración garantiza en producción, sin depender del orden.
        founder = ResCompany.get_founder()
        for key, value in FOUNDER_L1_SETTINGS.items():
            CompanySetting.set_setting(key, value, founder)

    def test_founder_has_its_own_seeded_contact_settings(self):
        founder = ResCompany.objects.get(code=FOUNDER_COMPANY_CODE)
        assert CompanySetting.get_setting(
            'contact.from_email', company=founder,
        ) == 'hola@practicayoruba.com'
        assert CompanySetting.get_setting(
            'contact.notify_email', company=founder,
        ) == 'hola@practicayoruba.com'
        assert CompanySetting.get_setting(
            'newsletter.from_email', company=founder,
        ) == 'newsletter@practicayoruba.com'
        # #199: remitente no-reply transaccional del founder (auth/órdenes/
        # envíos/devoluciones/soporte) — antes ``DEFAULT_FROM_EMAIL`` global.
        assert CompanySetting.get_setting(
            'notifications.from_email', company=founder,
        ) == 'noreply@practicayoruba.com'

    def test_neutral_fallback_is_not_practicayoruba_specific_for_other_company(self):
        other = _company('other-tenant-founder-seed')
        assert CompanySetting.get_setting(
            'contact.from_email', 'hola@kaupamex.com', company=other,
        ) == 'hola@kaupamex.com'

    def test_founder_seeding_is_idempotent_with_manual_seed(self):
        founder = ResCompany.objects.get(code=FOUNDER_COMPANY_CODE)
        # Re-crear la company founder es un no-op (get_or_create); confirma
        # que no hay una segunda fila duplicada de la migración.
        again, created = ResCompany.objects.get_or_create(
            code=FOUNDER_COMPANY_CODE,
            defaults={'name': 'PracticaYoruba', 'status': ResCompany.Status.ACTIVE},
        )
        assert created is False
        assert again.pk == founder.pk
        assert CompanySetting.objects.filter(
            company=founder, key='contact.from_email',
        ).count() == 1


class TestMeta:
    def test_key_is_unique_per_company_not_globally(self):
        acme = _company('acme-setting-10')
        globex = _company('globex-setting-10')
        # misma key en dos companies distintas: permitido (unique_together
        # es (company, key), no key sola).
        CompanySetting.objects.create(company=acme, key='dup.key', value='a')
        CompanySetting.objects.create(company=globex, key='dup.key', value='b')
        assert CompanySetting.objects.filter(key='dup.key').count() == 2

    def test_duplicate_company_key_pair_rejected(self):
        acme = _company('acme-setting-11')
        CompanySetting.objects.create(company=acme, key='dup.key', value='a')
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                CompanySetting.objects.create(company=acme, key='dup.key', value='b')

    def test_str_is_company_and_key(self):
        acme = _company('acme-setting-12')
        setting = CompanySetting.objects.create(
            company=acme, key='some.key', value='v',
        )
        assert str(setting) == f'{acme.pk}:some.key'
