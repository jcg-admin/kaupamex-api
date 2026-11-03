"""Aislamiento físico y por fila con PostgreSQL propio (TASK-API-0383).

El acceso a aliases dinámicos utiliza el fixture público django_db_blocker,
sin solicitar db/transactional_db ni alterar restricciones privadas de TestCase.
Cada ejecución adquiere nombres impredecibles, migra con el aprovisionador real
y elimina exclusivamente las bases cuya creación terminó correctamente.
Las filas de empresa desaparecen con sus bases; el caso N=1 revierte su escritura.
Esto verifica aislamiento de datos, no autenticación ni aceptación de la TASK.
"""
import os
import secrets
from contextlib import ExitStack, contextmanager

import pytest
from django.conf import settings
from django.db import connections, transaction

from addons.authz.models import Module
from addons.base.models import ResCompany
from addons.sale_subscription.models import CompanyModuleSubscription
from orm.environments import company_scope
from service import db as svc

pytestmark = pytest.mark.integration

_COMPANY_A_ID = secrets.randbits(48)
_COMPANY_B_ID = _COMPANY_A_ID + 1
_ALIAS_A = f'company_{_COMPANY_A_ID}_db'
_ALIAS_B = f'company_{_COMPANY_B_ID}_db'


def _require_disposable_default():
    """Rechaza QA compartida aunque alguien declare permiso de recreación."""
    name = settings.DATABASES['default']['NAME']
    if (not name.startswith(('orm_bootstrap_', 'kaupamex_ci_'))
            or os.environ.get('CI_DATABASE_DISPOSABLE') != name):
        raise RuntimeError('Isolation fixture requires an explicitly owned disposable default')


def _forget_alias(alias):
    """Cierra el wrapper antes de retirar su registro dinámico."""
    if alias in settings.DATABASES:
        connections[alias].close()
        del connections[alias]
        del settings.DATABASES[alias]


@contextmanager
def _company_databases(aliases):
    """No adquiere ni elimina aliases o bases preexistentes."""
    for alias in aliases:
        if alias in settings.DATABASES or svc.database_exists(alias):
            raise RuntimeError('Isolation fixture refuses an existing database or alias')
    with ExitStack() as resources:
        for alias in aliases:
            resources.callback(_forget_alias, alias)
        svc.install_company_aliases(settings.DATABASES, names=aliases)
        for alias in aliases:
            # CREATE DATABASE es exclusivo; las extensiones son best-effort del servicio.
            svc.create_empty_database(alias)
            resources.callback(svc.drop_database, alias)
            svc.provision_company_database(alias)
        yield aliases


@pytest.fixture(autouse=True)
def isolation_database_access(django_db_blocker):
    """Acceso explícito público; no se instala un TestCase para eludirlo después."""
    _require_disposable_default()
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope='module')
def two_company_databases(django_db_blocker):
    """Aprovisiona dos bases exclusivas con todas las migraciones vigentes."""
    _require_disposable_default()
    with django_db_blocker.unblock():
        with _company_databases((_ALIAS_A, _ALIAS_B)) as aliases:
            yield aliases


class TestN1DegenerationRealWrite:
    """Sin aliases de empresa, el dominio utiliza la base default propia."""

    def test_domain_write_without_any_company_alias_lands_in_default(self):
        assert not any(a.startswith('company_') for a in settings.DATABASES)
        with transaction.atomic(using='default'):
            with company_scope(999999):
                Module.objects.create(code='n1-degenerate', name='N1')
            assert Module.objects.using('default').filter(code='n1-degenerate').exists()
            transaction.set_rollback(True, using='default')


class TestCrossCompanyIsolationByBase:
    """T-091-07 — aislamiento por BASE entre dos companies reales."""

    def test_write_under_company_scope_lands_in_its_own_base(self, two_company_databases):
        alias_a, alias_b = two_company_databases
        with company_scope(_COMPANY_A_ID):
            Module.objects.create(code='iso-write-a', name='Aislado A')

        # PK no es identificador cross-base fiable: cada alias tiene su
        # propio autoincrement (dos filas "primera de su base" comparten
        # pk=1 aunque vivan en bases distintas) — se compara por 'code'
        # (unico, valor de negocio), no por pk.
        assert Module.objects.using(alias_a).filter(code='iso-write-a').exists()
        assert not Module.objects.using(alias_b).filter(code='iso-write-a').exists()

    def test_rows_from_company_a_not_visible_under_company_b_scope(self, two_company_databases):
        with company_scope(_COMPANY_A_ID):
            Module.objects.create(code='iso-a2', name='A2')

        with company_scope(_COMPANY_B_ID):
            # Bajo el scope de B, el router lee de la base B: la fila
            # de A (fisicamente en company_8801_db) NO existe ahi.
            assert not Module.objects.filter(code='iso-a2').exists()
            Module.objects.create(code='iso-b2', name='B2')

        with company_scope(_COMPANY_A_ID):
            assert not Module.objects.filter(code='iso-b2').exists()
            assert Module.objects.filter(code='iso-a2').exists()


class TestSol085RowScopingIntraBase:
    """T-091-08 — SOL-085 (row-scoping) sin regresión por el wiring del
    router + la FK ``company`` resuelve intra-base (D-091-2).

    Bajo multi-DB REAL (dos bases ``company_<N>_db`` registradas), se
    escriben DOS ``ResCompany`` + sus ``CompanyModuleSubscription`` bajo el
    MISMO ``company_scope`` (por lo tanto ambas parejas co-residen en la
    MISMA base física, ``alias_a``) — esto aisla la variable: cualquier
    diferencia entre lo que ve ``scoped`` vs ``objects`` es filtrado POR FILA
    (columna ``company_id``), no por base (que aquí es constante).
    """

    def test_row_scoping_filters_by_row_and_fk_resolves_intra_base(
        self, two_company_databases,
    ):
        alias_a, alias_b = two_company_databases

        with company_scope(_COMPANY_A_ID):
            module = Module.objects.create(code='cat-intra-base', name='Catalogue')
            # Dos ResCompany con FK ids explicitos, AMBAS escritas bajo el MISMO
            # company_scope(_COMPANY_A_ID) -> ambas ruteán a alias_a (D-091-2:
            # el FK 'company' de la suscripcion resuelve intra-base porque el
            # router las coloca a las dos en la misma base fisica).
            acme = ResCompany.objects.create(
                id=_COMPANY_A_ID, code='acme-intra-base', name='Acme',
            )
            globex = ResCompany.objects.create(
                id=_COMPANY_B_ID, code='globex-shadow-intra-base', name='Globex Shadow',
            )
            sub_acme = CompanyModuleSubscription.objects.create(
                company=acme, module=module,
                status=CompanyModuleSubscription.Status.ACTIVE,
            )
            sub_globex = CompanyModuleSubscription.objects.create(
                company=globex, module=module,
                status=CompanyModuleSubscription.Status.ACTIVE,
            )

            # SOL-085: el manager scopeado SOLO ve la fila de la company
            # activa (_COMPANY_A_ID) aunque sub_globex viva en la MISMA base
            # -- filtro por FILA (columna company_id), no por base.
            scoped_ids = set(
                CompanyModuleSubscription.scoped.for_current_company()
                .values_list('pk', flat=True)
            )
            assert scoped_ids == {sub_acme.pk}
            assert sub_globex.pk not in scoped_ids

            # El manager default (L0, cross-company) SI ve ambas -- confirma
            # que ambas conviven fisicamente en la misma base (sin lo cual
            # el FK de sub_globex -> globex ni siquiera hubiera podido
            # crearse: PostgreSQL exige claves foráneas dentro de la misma base).
            all_ids = set(
                CompanyModuleSubscription.objects.values_list('pk', flat=True)
            )
            assert all_ids == {sub_acme.pk, sub_globex.pk}

        # Confirmacion fisica fuera de cualquier scope: las 2 ResCompany + las 2
        # suscripciones viven en alias_a; nada se filtro a alias_b (aislamiento
        # por base, T-091-07, sigue intacto pese a que ambas companies
        # conceptuales co-residen aqui).
        assert ResCompany.objects.using(alias_a).filter(
            code__in=['acme-intra-base', 'globex-shadow-intra-base'],
        ).count() == 2
        assert CompanyModuleSubscription.objects.using(alias_a).filter(
            pk__in=[sub_acme.pk, sub_globex.pk],
        ).count() == 2
        assert CompanyModuleSubscription.objects.using(alias_b).count() == 0
        assert ResCompany.objects.using(alias_b).filter(
            code__in=['acme-intra-base', 'globex-shadow-intra-base'],
        ).count() == 0


def test_company_schemas_and_native_connections(two_company_databases):
    """Cada instalación conserva identidad física y FK locales sin overrides."""
    for alias in two_company_databases:
        connection = connections[alias]
        assert 'ensure_connection' not in connection.__dict__
        assert 'cursor' not in connection.__dict__
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), to_regclass('res_users'), to_regclass('django_content_type')")
            name, users, metadata = cursor.fetchone()
            assert name == alias and users and metadata
            cursor.execute("SELECT count(*) FROM pg_constraint c JOIN pg_class p ON p.oid=c.confrelid WHERE c.contype='f' AND p.relname='res_users'")
            assert cursor.fetchone()[0] > 0
