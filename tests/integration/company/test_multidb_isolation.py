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
from addons.base.models import (IrModelData, ReportPaperformat, ResCompany,
                                ResUsers)
from addons.sale_subscription.models import CompanyModuleSubscription
from orm.environments import Environment, company_scope
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


_EMPLOYEE_VIEW = 'hr_employee_public'


def _view_kind(alias):
    """``relkind`` de la vista en la base ``alias``, o ``None``."""
    with connections[alias].cursor() as cursor:
        cursor.execute('SELECT relkind FROM pg_class WHERE relname = %s',
                       [_EMPLOYEE_VIEW])
        row = cursor.fetchone()
        return row[0] if row else None


def _employee_public():
    """``hr.employee.public`` desde el registro de apps, sin import propio."""
    return ResCompany._meta.apps.get_model('hr', 'HrEmployeePublic')


def _drop_employee_view(alias):
    with connections[alias].cursor() as cursor:
        cursor.execute(f'DROP VIEW IF EXISTS {_EMPLOYEE_VIEW}')


def test_init_creates_the_view_only_in_the_selected_database(
        two_company_databases):
    """≙ ``model.init()`` en ``init_models`` (``odoo19c: odoo/orm/
    registry.py:751-752``) con el cursor de la base que se instala.

    1. el aprovisionamiento de cada base deja su vista (la crea el gancho
       desde el ciclo de instalación; ninguna migración la crea);
    2. ``init(using=A)`` la crea en A y no toca B ni la base por defecto;
    3. reejecutarlo conserva el resultado.
    Sin el ``using`` en el override, la vista cae en la base por defecto.
    """
    alias_a, alias_b = two_company_databases
    for alias in (alias_a, alias_b):
        assert _view_kind(alias) == 'v', alias
    default_before = _view_kind('default')
    _drop_employee_view(alias_a)
    _drop_employee_view(alias_b)

    _employee_public().init(using=alias_a)
    assert _view_kind(alias_a) == 'v'
    assert _view_kind(alias_b) is None
    assert _view_kind('default') == default_before

    _employee_public().init(using=alias_a)
    assert _view_kind(alias_a) == 'v'
    assert _view_kind(alias_b) is None

    _employee_public().init(using=alias_b)
    assert _view_kind(alias_b) == 'v'


# --- init(using=...) de res.company y res.users bajo alias ---------------
# Diseño: scripts/workbench/orm-continuation-plan-20261103T095630/designs/
# init-alias-propagation.md.

_PAPERFORMATS = ('paperformat_euro', 'paperformat_us',
                 'paperformat_batch_deposit')


def _euro_id(alias):
    row = IrModelData.objects.using(alias).get(
        module='base', name='paperformat_euro')
    return row.res_id


def _company_without_format(alias, code):
    # ``db_manager`` conserva ``ResCompanyManager.create``, que fabrica el
    # partner como la fuente (``res_company.py:296-300``); ``using`` daría
    # el ``QuerySet.create`` genérico, sin partner. El entorno de la base
    # lleva a ella las lecturas por router de los defaults (``stock``:
    # ``_default_confirmation_mail_template`` resuelve un XML-ID), que bajo
    # N>1 sin entorno ni empresa se rechazan.
    with Environment(alias):
        company = ResCompany.objects.db_manager(alias).create(name=code,
                                                              code=code)
    assert company._state.db == alias
    ResCompany.objects.using(alias).filter(pk=company.pk).update(
        paperformat=None)
    return company.pk


def _format_of(alias, pk):
    return ResCompany.objects.using(alias).filter(pk=pk).values_list(
        'paperformat_id', flat=True).get()


@pytest.fixture
def company_without_format_per_base(two_company_databases):
    """Una compañía sin formato en A, en B y en ``default``; se retiran al
    terminar para no dejar filas a los demás casos."""
    alias_a, alias_b = two_company_databases
    rows = {alias: _company_without_format(alias, f'init-{alias}')
            for alias in (alias_a, alias_b, 'default')}
    yield rows
    for alias, pk in rows.items():
        with Environment(alias):
            ResCompany.objects.db_manager(alias).filter(pk=pk).delete()


def test_paperformat_xml_ids_exist_in_every_base(two_company_databases):
    """La siembra de ``base/0107`` corre en cada base aprovisionada y cada
    XML-ID apunta a una fila de su propia base."""
    for alias in (*two_company_databases, 'default'):
        for name in _PAPERFORMATS:
            row = IrModelData.objects.using(alias).get(module='base',
                                                       name=name)
            assert ReportPaperformat.objects.using(alias).filter(
                pk=row.res_id).exists(), (alias, name)


def test_company_init_writes_only_the_selected_base(
        two_company_databases, company_without_format_per_base):
    """≙ ``init`` con el cursor de la base que se instala
    (``odoo19c: odoo/orm/registry.py:741-752``): sin empresa activa la
    escritura cae en B, y ni A ni ``default`` cambian."""
    alias_a, alias_b = two_company_databases
    rows = company_without_format_per_base
    ResCompany.init(using=alias_b)
    assert _format_of(alias_b, rows[alias_b]) == _euro_id(alias_b)
    assert _format_of(alias_a, rows[alias_a]) is None
    assert _format_of('default', rows['default']) is None
    # Reejecución: idempotente.
    ResCompany.init(using=alias_b)
    assert _format_of(alias_b, rows[alias_b]) == _euro_id(alias_b)
    assert _format_of(alias_a, rows[alias_a]) is None


def test_company_init_ignores_the_active_company_scope(
        two_company_databases, company_without_format_per_base):
    """El alias de ``init`` manda sobre la empresa activa, como el ``env.cr``
    de la fuente manda sobre la compañía del contexto."""
    alias_a, alias_b = two_company_databases
    rows = company_without_format_per_base
    with company_scope(_COMPANY_A_ID):
        ResCompany.init(using=alias_b)
    assert _format_of(alias_b, rows[alias_b]) == _euro_id(alias_b)
    assert _format_of(alias_a, rows[alias_a]) is None


def test_company_init_without_the_xml_id_assigns_nothing_and_rolls_back(
        two_company_databases, company_without_format_per_base):
    alias_a, alias_b = two_company_databases
    rows = company_without_format_per_base
    with transaction.atomic(using=alias_b):
        # El borrado pasa por el colector y sus señales (``base_automation``
        # lee por el router): en el entorno de B, como todo borrado de la
        # fuente.
        with Environment(alias_b):
            IrModelData.objects.using(alias_b).filter(
                module='base', name='paperformat_euro').delete()
        ResCompany.init(using=alias_b)
        assert _format_of(alias_b, rows[alias_b]) is None
        transaction.set_rollback(True, using=alias_b)
    assert IrModelData.objects.using(alias_b).filter(
        module='base', name='paperformat_euro').exists()


def _password(alias, uid):
    return ResUsers.objects.using(alias).filter(pk=uid).values_list(
        'password', flat=True).get()


def test_users_init_encrypts_only_in_the_selected_base(
        two_company_databases):
    """La contraseña en claro de B se cifra; la de A sigue en claro; la de
    ``default`` no cambia. Se restauran los valores originales."""
    alias_a, alias_b = two_company_databases
    uids = {alias: ResUsers.objects.using(alias).order_by('pk')
            .values_list('pk', flat=True).first()
            for alias in (alias_a, alias_b, 'default')}
    original = {alias: _password(alias, uid) for alias, uid in uids.items()}
    try:
        for alias in (alias_a, alias_b):
            ResUsers.objects.using(alias).filter(pk=uids[alias]).update(
                password='clave-en-claro')
        ResUsers.init(using=alias_b)
        stored_b = _password(alias_b, uids[alias_b])
        assert ResUsers._crypt_context().identify(stored_b) != 'plaintext'
        assert ResUsers._crypt_context().verify('clave-en-claro', stored_b)
        assert _password(alias_a, uids[alias_a]) == 'clave-en-claro'
        assert _password('default', uids['default']) == original['default']
    finally:
        for alias, uid in uids.items():
            ResUsers.objects.using(alias).filter(pk=uid).update(
                password=original[alias])


def test_init_models_runs_both_inits_in_the_selected_base(
        two_company_databases, company_without_format_per_base):
    alias_a, alias_b = two_company_databases
    rows = company_without_format_per_base
    uid = ResUsers.objects.using(alias_b).order_by('pk').values_list(
        'pk', flat=True).first()
    original = _password(alias_b, uid)
    try:
        ResUsers.objects.using(alias_b).filter(pk=uid).update(
            password='otra-clave')
        # ≙ ``env.registry`` de la base B.
        registry = Environment(alias_b).registry
        with connections[alias_b].cursor() as cr:
            registry.init_models(cr, ['res.company', 'res.users'],
                                 {'module': 'base'}, install=False)
        assert _format_of(alias_b, rows[alias_b]) == _euro_id(alias_b)
        assert _format_of(alias_a, rows[alias_a]) is None
        assert ResUsers._crypt_context().identify(
            _password(alias_b, uid)) != 'plaintext'
    finally:
        ResUsers.objects.using(alias_b).filter(pk=uid).update(
            password=original)
