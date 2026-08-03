"""Integración — aislamiento físico multi-DB DB-per-company (SOL-091, T-091-07/08).

Prueba el aislamiento **por BASE** (no por fila): bajo ``company_scope(A)`` una
escritura de dominio aterriza en ``company_A_db``; bajo ``company_scope(B)``
las filas de A **no** son visibles — son bases físicas distintas, no un filtro
de columna. Complementa a ``tests/unit/orm/test_multidb_router.py`` (lógica
pura del router, mockeada) y a ``tests/unit/orm/test_router_failclosed.py``
(fail-closed, mockeado): este archivo es el primero de la iniciativa que
provisiona bases ``company_<N>_db`` **reales** contra MariaDB ejerciendo el
ORM (``company_scope`` + router) dentro del propio suite de pytest — el
precedente ``tests/integration/service/test_db_provision.py`` (T-091-06) ya
prueba DDL real (``create_empty_database``/``drop_database``/…) pero siempre
vía la conexión ``default`` con nombres de tabla calificados (``` `company_9001_db`.widget ```),
nunca conectando el ORM a un alias separado — no cubre el camino
``company_scope`` → router → alias que T-091-07/08 necesitan probar.

Dos gotchas empíricos documentados en el mismo pase (hallazgos H-API-091-07 y
H-API-091-08 en ``hallazgos-implementar-aislamiento-multi-db-per-company.rst``):

1. **H-API-091-07** — ``service.db.provision_company_database`` (el
   primitivo de T-091-06) hace ``migrate --run-syncdb`` de **todas** las
   apps. Contra una base ``company_<N>_db`` real eso revienta hoy con dos
   causas distintas: (a) ``django.contrib.admin``/``django.contrib.auth`` no
   están en ``MULTIDB_CONTROL_PLANE_APPS`` (sólo
   ``sessions``/``contenttypes``/``base``) pero sus tablas
   (``django_admin_log``, ``auth_permission``) tienen FK a
   ``django_content_type``, que SÍ es control-plane (vive sólo en
   ``default``) — MariaDB rechaza el ``CREATE TABLE`` con errno 150; (b) con
   esas dos apps parcheadas como control-plane, el ``RunPython`` de alta de
   datos ``addons/orders/migrations/0002_seed_shipping_zones.py`` escribe
   ``ShippingZone.objects.get_or_create(...)`` sin ``company_scope`` activo —
   una vez hay ALGÚN alias ``company_*`` registrado (N>1 global), el guard
   fail-closed de ``CompanyDatabaseRouter._route`` lo rechaza con
   ``CompanyContextRequired``. Por eso estos tests **no** usan
   ``provision_company_database`` para el schema completo — usan sus mismos
   primitivos (``create_empty_database`` + ``migrate <app_label>``, PROVEN
   empíricamente) acotados a las apps de dominio que el test necesita
   (``authz`` para ``Module``; ``company`` para
   ``Company``/``CompanyModuleSubscription``).
2. **H-API-091-08** — tres gotchas de arnés (harness) encadenados al
   intentar conectar el ORM a un alias ``company_<N>_db`` DINÁMICO dentro
   de un test de pytest-django (nunca antes ejercido en este suite — el
   precedente ``test_db_provision.py`` sólo usa DDL vía ``default`` con
   nombres de tabla calificados, jamás abre una conexión ORM real al alias):

   a. Inyectar el alias a mitad de un test con
      ``override_settings(DATABASES=...)`` NO conecta:
      ``django.db.connections`` cachea el dict de settings UNA sola vez
      (``BaseConnectionHandler.settings`` es un ``cached_property``);
      ``override_settings`` reemplaza el objeto por uno nuevo y el cache de
      ``connections`` sigue apuntando al viejo. La vía que sí funciona (la
      que usa ``service.db.install_company_aliases`` en producción) es
      mutar el MISMO dict in-place — por eso el registro del alias es
      ``scope='module'`` (corre antes que el ``setUpClass`` de CUALQUIER
      test del módulo, ver ``two_company_databases``).
   b. Un fixture ``scope='module'`` que hace I/O de DB corre ANTES de que
      pytest-django habilite el acceso a la base (eso lo hace el autouse
      ``_django_db_helper``, ``function``-scope, que se resuelve después)
      — se resuelve pidiendo el fixture ``django_db_blocker`` (``session``
      -scope) y envolviendo el cuerpo en ``.unblock()``.
   c. Declarar los 2 alias vía ``databases='__all__'`` en el marker
      ``django_db`` los vuelve blanco del ``flush`` automático que Django
      corre al final de CADA test transaccional — pero el ``post_migrate``
      de ese ``flush`` (``auth.create_permissions`` /
      ``contenttypes.create_contenttypes``) asume que ``django_content_type``
      existe en CUALQUIER base, y revienta porque estas 2 bases
      deliberadamente NO tienen contenttypes (control-plane, punto 1).
   d. Sin declarar los alias en el marker, ``TestCase.databases`` (un
      mecanismo DISTINTO del blocker de pytest-django: un
      ``mock.patch.object(BaseDatabaseWrapper, "ensure_connection", ...)``
      que Django aplica a nivel de CLASE en cada ``setUpClass``) rechaza
      cualquier query a ``company_88xx_db`` con ``DatabaseOperationForbidden``.
      ``django_db_blocker.unblock()`` **no alcanza** para revertir esto — es
      un blocker de una capa distinta (el de pytest-django, no el de
      ``TestCase``) y depender del orden relativo de fixtures autouse para
      que uno pise al otro resultó frágil incluso forzando la dependencia
      explícita. La resolución robusta: pinchear el ``ensure_connection``
      GENUINO (``django_db_blocker._real_ensure_connection`` — el que el
      propio blocker de pytest-django cachea antes de bloquear nada, en
      ``pytest_configure``, muy anterior a la colección de este módulo; NO
      es fiable capturarlo uno mismo a nivel de módulo porque para cuando
      pytest importa este archivo, ``BaseDatabaseWrapper.ensure_connection``
      YA es el wrapper bloqueante de pytest-django, no el original) como
      atributo de INSTANCIA en los wrappers de conexión de
      ``company_8801_db``/``company_8802_db`` — un atributo de instancia
      siempre gana sobre uno de clase en la resolución de atributos de
      Python, así que esto anula el patch de ``TestCase`` para estas 2
      conexiones específicas sin importar el orden de fixtures.
"""
import types

import pytest

from django.conf import settings
from django.core.management import call_command
from django.db import connections

from addons.authz.models import Module
from addons.platform.context import company_scope
from addons.platform.models import Company, CompanyModuleSubscription
from service import db as svc

pytestmark = [
    pytest.mark.integration,
    # transaction=True: el DDL de provisioning (CREATE/DROP DATABASE,
    # autocommit en MariaDB) rompería el wrapper atómico de un django_db
    # normal (mismo criterio que test_db_provision.py, T-091-06).
    #
    # OJO: NO se usa databases='__all__' aquí (gotcha empírico, ver
    # '_unblock_extra_company_dbs' más abajo): declarar company_88xx_db en
    # TestCase.databases hace que Django dispare un 'flush' automático de
    # esas 2 bases al final de CADA test — su post_migrate (auth
    # create_permissions/contenttypes create_contenttypes) asume que
    # django_content_type existe en CUALQUIER base, y revienta porque estas
    # 2 bases deliberadamente NO tienen contenttypes (control-plane, ver
    # H-API-091-07). El acceso a esos 2 alias se habilita en su lugar sin
    # declararlos (fixture '_unblock_extra_company_dbs' más abajo).
    pytest.mark.django_db(transaction=True),
]

_ALIAS_A = 'company_8801_db'
_ALIAS_B = 'company_8802_db'
_COMPANY_A_ID = 8801
_COMPANY_B_ID = 8802


def _provision(alias):
    """Alta de una base ``company_<N>_db`` real, acotada a ``authz`` +
    ``company`` (ver H-API-091-07 en el docstring del módulo) — NO usa
    ``provision_company_database`` para no tropezar con ese hallazgo.
    """
    svc.create_empty_database(alias)
    call_command('migrate', 'authz', database=alias, verbosity=0)
    call_command('migrate', 'platform', database=alias, verbosity=0)


def _forget_alias(alias):
    """Revierte el registro: quita la entrada de ``settings.DATABASES`` y
    evita que ``connections`` conserve el wrapper (ya cerrado) en el
    almacenamiento thread-local (``ConnectionHandler.__delitem__``).
    """
    if alias in settings.DATABASES:
        del settings.DATABASES[alias]
    try:
        del connections[alias]
    except AttributeError:
        # silent OK because nunca se instanció una conexión real para este
        # alias (p.ej. si provisionar falló antes de la primera migración) —
        # no hay nada que desregistrar.
        pass


# Los 4 métodos que Django envuelve en instancia con _DatabaseFailure para
# cualquier alias fuera de cls.databases (ver
# django.test.testcases.SimpleTestCase._disallowed_connection_methods).
_DISALLOWED_CONNECTION_METHODS = ('connect', 'temporary_connection', 'cursor', 'chunked_cursor')


def _unpatch_test_case_restriction(alias, real_ensure_connection):
    """Revierte, para el wrapper de conexión de ``alias``, LAS DOS capas que
    ``TestCase.databases`` (Django, no el blocker de pytest-django) aplica
    en cada ``setUpClass`` (ver punto (d) del docstring del módulo):

    1. ``connection.cursor``/``connect``/``temporary_connection``/
       ``chunked_cursor`` — Django los reemplaza por instancia con
       ``_DatabaseFailure`` para todo alias fuera de ``cls.databases``.
       Basta con BORRAR el atributo de instancia: sin él, la resolución de
       atributos cae de vuelta al método normal de la CLASE del wrapper.
    2. ``ensure_connection`` — Django lo reemplaza a nivel de CLASE
       (``BaseDatabaseWrapper``, afecta a TODOS los alias). Se ancla el
       genuino (``real_ensure_connection``, cacheado por el propio blocker
       de pytest-django) como atributo de instancia (gana sobre el de
       clase) SOLO para este wrapper puntual.
    """
    conn = connections[alias]
    for name in _DISALLOWED_CONNECTION_METHODS:
        if name in conn.__dict__:
            del conn.__dict__[name]
    conn.ensure_connection = types.MethodType(real_ensure_connection, conn)


@pytest.fixture(autouse=True)
def _unblock_extra_company_dbs(db, django_db_blocker):
    """Revierte el patch de ``TestCase.databases`` en cada test (Django lo
    re-aplica en CADA ``setUpClass``, así que hay que revertirlo en CADA
    test) para los 2 alias, si ya están registrados (``two_company_databases``
    los registra en ``settings.DATABASES`` la primera vez que algún test los
    solicita; los tests que no la piden — p. ej.
    ``TestN1DegenerationRealWrite`` — no tienen nada que revertir todavía).
    """
    real_ensure_connection = django_db_blocker._real_ensure_connection
    for alias in (_ALIAS_A, _ALIAS_B):
        if alias in settings.DATABASES:
            _unpatch_test_case_restriction(alias, real_ensure_connection)
    yield


@pytest.fixture(scope='module')
def two_company_databases(django_db_blocker):
    """Dos bases físicas reales ``company_8801_db`` / ``company_8802_db``,
    compartidas por TODOS los tests de este módulo que la soliciten.

    ``scope='module'`` (no por-test, ver H-API-091-08 en el docstring del
    módulo): un fixture ``scope='module'`` se instala ANTES que cualquier
    fixture ``function``-scope del primer test que lo solicita (los scopes
    más amplios se instalan primero) — incluyendo el autouse
    ``_django_db_helper`` que normalmente habilita el acceso a DB. Sin
    desbloquear explícitamente aquí (``django_db_blocker.unblock()``), el
    primer ``create_empty_database`` revienta con
    ``RuntimeError: Database access not allowed``.

    Al no declarar estos 2 alias en ``TestCase.databases`` (ver
    ``pytestmark``), Django NUNCA los toca en su ``flush`` automático
    por-test — las filas que cada test escribe persisten entre tests DENTRO
    del módulo (de ahí que cada test use ``code``/``id`` únicos, nunca
    asuma "tabla vacía"). El DROP físico ocurre UNA sola vez, al final del
    módulo.
    """
    with django_db_blocker.unblock():
        svc.install_company_aliases(settings.DATABASES, names=[_ALIAS_A, _ALIAS_B])
        try:
            _provision(_ALIAS_A)
            _provision(_ALIAS_B)
            yield _ALIAS_A, _ALIAS_B
        finally:
            svc.drop_database(_ALIAS_A)
            svc.drop_database(_ALIAS_B)
            _forget_alias(_ALIAS_A)
            _forget_alias(_ALIAS_B)


class TestN1DegenerationRealWrite:
    """T-091-07 (caso N=1) — sin NINGÚN alias ``company_<N>_db`` registrado,
    el router degenera a ``default`` (H-API-091-06), verificado con una
    escritura ORM real (no mockeada). Va PRIMERO en el archivo (antes de que
    ``two_company_databases`` registre cualquier alias) para que su premisa
    ("cero alias company_* activos") sea verificable de verdad — no un
    supuesto.
    """

    def test_domain_write_without_any_company_alias_lands_in_default(self):
        assert not any(a.startswith('company_') for a in settings.DATABASES)
        with company_scope(999999):  # ninguna company_999999_db existe
            Module.objects.create(code='n1-degenerate', name='N1')
        assert Module.objects.using('default').filter(code='n1-degenerate').exists()


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
            # Bajo el scope de B, el router lee de company_8802_db: la fila
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
    escriben DOS ``Company`` + sus ``CompanyModuleSubscription`` bajo el
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
            # Dos Company con FK ids explicitos, AMBAS escritas bajo el MISMO
            # company_scope(_COMPANY_A_ID) -> ambas ruteán a alias_a (D-091-2:
            # el FK 'company' de la suscripcion resuelve intra-base porque el
            # router las coloca a las dos en la misma base fisica).
            acme = Company.objects.create(
                id=_COMPANY_A_ID, code='acme-intra-base', name='Acme',
            )
            globex = Company.objects.create(
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
            # crearse: MariaDB/InnoDB no soporta FK cross-schema).
            all_ids = set(
                CompanyModuleSubscription.objects.values_list('pk', flat=True)
            )
            assert all_ids == {sub_acme.pk, sub_globex.pk}

        # Confirmacion fisica fuera de cualquier scope: las 2 Company + las 2
        # suscripciones viven en alias_a; nada se filtro a alias_b (aislamiento
        # por base, T-091-07, sigue intacto pese a que ambas companies
        # conceptuales co-residen aqui).
        assert Company.objects.using(alias_a).filter(
            code__in=['acme-intra-base', 'globex-shadow-intra-base'],
        ).count() == 2
        assert CompanyModuleSubscription.objects.using(alias_a).filter(
            pk__in=[sub_acme.pk, sub_globex.pk],
        ).count() == 2
        assert CompanyModuleSubscription.objects.using(alias_b).count() == 0
        assert Company.objects.using(alias_b).filter(
            code__in=['acme-intra-base', 'globex-shadow-intra-base'],
        ).count() == 0
