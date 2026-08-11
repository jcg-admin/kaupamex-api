"""
conftest.py — Fixtures globales para PracticaYoruba API tests.
BD: kaupamex_qa (config.settings.testing)
"""
from pathlib import Path
from django.contrib.auth import get_user_model
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache

from addons.authz_password_policy.data import seed as password_policy_seed
from addons.authz_signup.data import seed as signup_flags_seed
from addons.authz_totp.data import seed as totp_params_seed
from addons.authz.models import Role, RoleAssignment
from addons.authz.services import SUPERADMIN_ROLE_CODE
from addons.base.models import SystemParameter
from addons.base.security.base_security import seed as base_rules_seed
from addons.base.data.res_country_data import seed as countries_seed
from addons.base_geolocalize.data import seed as geo_providers_seed
from addons.sale.data.report_templates import seed as sale_report_view_seed
from addons.sale.security.ir_rules import seed as sale_rules_seed
from addons.sale_stock.data.report_templates import (
    seed as incoterm_extension_seed,
)
from addons.sale_subscription.security.ir_rules import (
    seed as subscription_rules_seed,
)
from addons.sale_subscription.data.res_company_data import (
    seed as bootstrap_company_seed,
)
from addons.mail.data import seed as mail_subtypes_seed
from tests.factories.user_factory import make_buyer  # noqa: F401 (re-export)

import pytest
from addons.base.models.ir_config_parameter import _clear_cache as _clear_param_cache
from pytest_django.plugin import blocking_manager_key

# ─── Paths del repositorio ───────────────────────────────────────────────────
# Construidos relativos a este archivo — portables entre entornos.
_TESTS_DIR = Path(__file__).resolve().parent        # tests/
_REPO_ROOT  = _TESTS_DIR.parent                     # kaupamex-api/



@pytest.fixture
def user(db):
    """Usuario basico activo (party: ResUsers + ResPartner).

    ``res.users`` delega la identidad al partner (``_inherits`` de la
    referencia, ``odoo19c: base/models/res_users.py``): el nombre humano vive
    en ``ResPartner.name``, no en la credencial. El manager crea el partner
    cuando no se le pasa uno.
    """
    User = get_user_model()
    u = User.objects.create_user(
        login='test@practicayoruba.mx', password='TestPass123!',
        name='Test User',
    )
    return make_buyer(u)


@pytest.fixture
def auth_user(db):
    """Usuario independiente usado en tests de payment y sale."""
    User = get_user_model()
    u = User.objects.create_user(
        login='auth@practicayoruba.mx', password='AuthPass123!',
        name='Auth User',
    )
    return make_buyer(u)


@pytest.fixture
def admin_user(db):
    """Usuario staff. is_staff ya no existe: el acceso admin es una capacidad;
    se le asigna el rol superadmin (bypass del resolver, DEC-01=B)."""
    User = get_user_model()
    u = User.objects.create_user(
        login='admin@practicayoruba.mx', password='AdminPass123!',
        name='Admin User',
    )
    # ``EmployeeProfile`` no existe en la referencia: el empleado es el campo
    # ``employee`` de ``res.partner`` (odoo19c: base/models/res_partner.py).
    u.partner.employee = True
    u.partner.save(update_fields=['employee'])
    role, _ = Role.objects.get_or_create(
        code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
    )
    RoleAssignment.objects.get_or_create(user=u, role=role)
    return u


@pytest.fixture
def api_client():
    """Cliente REST sin autenticar."""
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Cliente REST autenticado por sesion de servidor (ADR-018).

    Tras la migracion a sesion (Opcion 3), la auth del web es la cookie de
    sesion, no JWT Bearer. ``force_login`` establece la sesion; el Bearer ya no
    lo lee el default auth (SessionAuthentication). Los tests de JWT dedicados
    (``test_jwt_endpoints``) siguen usando su propio flujo.
    """
    api_client.force_login(user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Cliente REST autenticado como admin por sesion de servidor."""
    api_client.force_login(admin_user)
    return api_client


@pytest.fixture
def admin_auth_client(api_client, admin_user):
    """Cliente REST autenticado como administrador por sesion de servidor."""
    api_client.force_login(admin_user)
    return api_client


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """
    Limpia el cache de rate limiting antes y después de cada test.
    Sin esto, los tests de login con credenciales incorrectas acumulan
    el contador de la IP 127.0.0.1 y bloquean tests subsecuentes.
    Solo limpia claves de rate limiting (prefijos login_fails: y pw_reset:).
    """

    def clear_rl():
        # Django LocMemCache no tiene método de scan — usamos cache.clear()
        # que también borra mail.outbox no (son estructuras independientes).
        # En producción con Redis se usaría cache.delete_many(pattern).
        cache.clear()

    clear_rl()
    yield
    clear_rl()

@pytest.fixture(autouse=True)
def _reset_system_parameter_cache():
    """Aísla la caché de parámetros entre tests.

    ``SystemParameter`` cachea a nivel de módulo (``_PARAM_CACHE``, el
    equivalente del ``ormcache`` de Odoo). La caché es per-proceso: el
    rollback de la transacción del test revierte la FILA, pero no el valor
    ya cacheado, así que un test que escribe un parámetro se lo filtra a
    todos los siguientes.

    Se destapó al mover los ajustes del sitio a parámetros (H-API-265):
    ``test_admin_can_update_iva_rate`` fijaba ``account.iva_rate`` a 0.08 y
    seis tests de ``sale`` calculaban su IVA con ese valor. Sin el reset,
    ``sale/`` da 8 fallos tras ``config/`` y 2 en solitario.
    """
    _clear_param_cache()
    yield
    _clear_param_cache()


# ─── Catálogo de semillas restauradas (H-API-22) ─────────────────────────────
# Verificado 2026-07-28 en kaupamex_qa: tras re-aplicar las semillas
# (system_parameter=3, mail_message_subtype=2, base_geo_provider=2), un único
# test transaccional las dejó las tres en 0.
#
# Cada addon expone su ``data.seed()`` idempotente — el equivalente nativo del
# ``data/*.xml`` que Odoo re-aplica al actualizar el módulo, y el mismo patrón
# que ``base`` ya usaba (``_DEFAULT_PARAMETERS`` + ``SystemParameter.seed()``).
# La migración importa **el mismo spec**, así que no hay dos copias que puedan
# divergir.
#
# Cubre las semillas de **configuración y catálogo** — las que producción
# siempre tiene y cuya ausencia vuelve order-dependent a los tests. NO cubre las
# data-migrations que son **portes históricos** de una sola vez (copiar applog a
# irlogging, retirar los modelos de cart, portar borradores a sale…): re-correr
# esas sería incorrecto, no una restauración.
#
# Exclusión deliberada: ``orders/0002_seed_shipping_zones``. Sembrar zonas de
# envío en cada test colisiona con los tests que crean las suyas y afirman
# conteos — el mismo choque que ya costó un CI rojo. Queda registrado como
# hallazgo aparte en vez de arrastrarlo aquí a ciegas.
_SEEDERS = (
    SystemParameter.seed,       # base/0002 + base/0003 (_DEFAULT_PARAMETERS)
    countries_seed,             # base/0017 (251 países + 8 agrupaciones)
    password_policy_seed,       # authz_password_policy/0001
    signup_flags_seed,          # authz_signup/0001
    totp_params_seed,           # authz_totp/0001 + 0002
    mail_subtypes_seed,         # mail/0002
    geo_providers_seed,         # base_geolocalize/0002
    bootstrap_company_seed,     # BOOTSTRAP_COMPANY_CODE (no-op si no se declara)
    base_rules_seed,            # base/security (record rules multi-company)
    sale_rules_seed,            # sale/security/ir_rules
    subscription_rules_seed,    # sale_subscription/security/ir_rules
    sale_report_view_seed,      # sale/0002 (plantilla del documento)
    incoterm_extension_seed,    # sale_stock/0003 — después de la primaria
)


@pytest.fixture(scope='session', autouse=True)
def _sembrar_al_inicio_de_sesion(django_db_setup, django_db_blocker):
    """Re-aplica el catálogo de semillas una vez al arrancar la sesión.

    El hook de teardown repara **después** de un test transaccional, pero no
    puede reparar lo que ya estaba roto: con ``--reuse-db``, un flush de una
    sesión anterior deja el schema sin semillas y ``django_migrations`` las
    sigue dando por aplicadas, así que la sesión siguiente arranca en rojo y
    el fallo aparece lejos de su causa (una vista de reporte que "no existe").

    Medido: la plantilla ``sale.report_saleorder`` sembrada por ``sale.0002``
    desapareció del schema de QA y tres tests del motor de reportes fallaban
    desde un arranque limpio. Con esta siembra de sesión, el orden de
    ejecución —y el historial del schema reusado— dejan de importar.
    """
    with django_db_blocker.unblock():
        for seed in _SEEDERS:
            seed()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    """Re-siembra las semillas tras un test transaccional — H-API-22.

    **Por qué un hook y no un fixture.** El ``flush`` vive en el teardown del
    fixture ``db``, y ``db`` se instala *antes* que los fixtures autouse del
    conftest, así que se finaliza *después* que ellos: ningún finalizador de
    fixture puede correr después del flush. Medido: un fixture que re-sembraba
    en su teardown escribía las filas (``sp=9``) y el flush posterior las
    borraba igual (``sp=0`` en la BD). ``pytest_runtest_teardown`` envuelto
    como ``hookwrapper`` sí corre después de **todos** los finalizadores.

    La alternativa —sembrar como precondición de cada test— también funciona,
    pero paga el costo ~600 veces para arreglar algo que ocurre 14. Aquí el
    costo es cero salvo tras un transaccional.

    ``unblock()`` es necesario: en este punto pytest-django ya volvió a
    bloquear el acceso a BD. Y la escritura queda **comiteada**, porque fuera
    de la transacción del test — que es justo lo que hace falta para que
    sobreviva al resto de la sesión.
    """
    yield
    marker = item.get_closest_marker('django_db')
    if marker is None:
        return
    if not (marker.kwargs.get('transaction')
            or (marker.args and marker.args[0])):
        return
    with item.config.stash[blocking_manager_key].unblock():
        for seed in _SEEDERS:
            seed()


# ─── Objetos SQL: retirados (H-DB-01) ───────────────────────────────────────
# Aquí vivía ``db_objects_setup``, que reinstalaba 3 funciones + 3 vistas + 3
# SPs desde el repo hermano ``<prefijo>-db`` cada vez que pytest-django
# recreaba el schema. Los nueve objetos se eliminaron de ``db``: la referencia
# no lleva lógica de negocio en SQL —0 ``CREATE PROCEDURE``/``FUNCTION`` en sus
# 78 ``.sql``— y declara sus vistas desde Python (``_auto = False`` +
# ``_table_query``), así que el ORM sigue siendo la fuente.
#
# El fixture no se sustituye por nada: sin objetos que instalar no hay paso que
# dar. Si vuelve a hacer falta una vista de reporte, se declara como modelo
# Python en el addon dueño, y entonces la crea la migración — no un fixture.
