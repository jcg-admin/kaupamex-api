"""
conftest.py — Fixtures globales para PracticaYoruba API tests.
BD: practicayoruba_qa (config.settings.testing)
"""
import os
import shutil
import subprocess
import time
from pathlib import Path
from django.contrib.auth import get_user_model
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache

from apps.platform.authz.models import Role, RoleAssignment
from apps.platform.authz.services import SUPERADMIN_ROLE_CODE
from apps.modules.users.models import EmployeeProfile, Person
from tests.factories.user_factory import make_buyer  # noqa: F401 (re-export)

import pytest
import warnings

# ─── Paths del repositorio ───────────────────────────────────────────────────
# Construidos relativos a este archivo — portables entre entornos.
_TESTS_DIR = Path(__file__).resolve().parent        # tests/
_REPO_ROOT  = _TESTS_DIR.parent                     # PracticaYoruba-api/
_DB_QA_SCRIPT = (
    _REPO_ROOT / 'scripts' / 'provisioners' / 'mysql' / 'db_qa_setup.sh'
)



@pytest.fixture
def user(db):
    """Usuario basico activo (party: IdentityUser + Person)."""
    User = get_user_model()
    u = User.objects.create_user(
        email='test@practicayoruba.mx', password='TestPass123!',
    )
    Person.objects.create(identity=u, first_name='Test', last_name='User')
    return make_buyer(u)


@pytest.fixture
def auth_user(db):
    """Usuario independiente usado en tests de payments y orders."""
    User = get_user_model()
    u = User.objects.create_user(
        email='auth@practicayoruba.mx', password='AuthPass123!',
    )
    Person.objects.create(identity=u, first_name='Auth', last_name='User')
    return make_buyer(u)


@pytest.fixture
def admin_user(db):
    """Usuario staff. is_staff ya no existe: el acceso admin es una capacidad;
    se le asigna el rol superadmin (bypass del resolver, DEC-01=B)."""
    User = get_user_model()
    u = User.objects.create_user(
        email='admin@practicayoruba.mx', password='AdminPass123!',
    )
    EmployeeProfile.objects.create(identity=u)
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

# ─── MariaDB Keepalive (ADR-008) ─────────────────────────────────────
# En este entorno MariaDB corre sin systemd y puede morir durante
# suites largas. El fixture reinicia automáticamente si detecta caída.


def _mariadb_alive() -> bool:
    # D-028: en MariaDB 11.x el binario es 'mariadb-admin' (NO 'mysqladmin').
    # Resolver el que exista. NO silenciar la ausencia de AMBOS: sin binario el
    # keepalive trataria una BD sana como caida y correria db_qa_setup + 30s de
    # sleep en CADA test (error silencioso). Se avisa fuerte en vez de mentir.
    admin_bin = shutil.which('mariadb-admin') or shutil.which('mysqladmin')
    if admin_bin is None:
        warnings.warn(
            "mariadb_keepalive: ni 'mariadb-admin' ni 'mysqladmin' en PATH "
            "(D-028) — no se puede verificar el estado de MariaDB.",
            RuntimeWarning, stacklevel=2,
        )
        return False
    # Ping por socket (canonico, ADR-008) con fallback a TCP.
    socket_path = os.environ.get('DB_QA_SOCKET', '') or '/run/mysqld/mysqld.sock'
    for cmd in (
        [admin_bin, 'ping', '--silent', f'--socket={socket_path}'],
        [admin_bin, 'ping', '--silent', '--host=127.0.0.1', '--port=3306'],
    ):
        try:
            if subprocess.run(cmd, capture_output=True, timeout=5).returncode == 0:
                return True
        except Exception:
            continue
    return False


def _restart_mariadb() -> bool:
    """
    Intenta restablecer el entorno de BD ejecutando db_qa_setup.sh.
    Retorna True si MariaDB responde en los 30 segundos siguientes.

    Nota: este script recrea el schema QA si es necesario — no reinicia
    el proceso de MariaDB directamente. En entornos sin systemd el proceso
    debe ser arrancado externamente; este helper solo reaplica el setup.
    Ver testing.py y ADR-008 para el contexto completo.
    """
    if not _DB_QA_SCRIPT.exists():
        # No silenciar — en un entorno nuevo el path debe existir.
        # Si no existe, hay un problema de configuración del repositorio.
        warnings.warn(
            f"mariadb_keepalive: script no encontrado: {_DB_QA_SCRIPT}\n"
            f"  El fixture no puede restablecer la BD automáticamente.\n"
            f"  Verifica que el repositorio esté en el estado correcto.",
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    result = subprocess.run(
        ['bash', str(_DB_QA_SCRIPT)],
        capture_output=True,
        timeout=90,
    )

    if result.returncode != 0:
        stderr_snippet = result.stderr.decode('utf-8', errors='replace')[:500]
        warnings.warn(
            f"mariadb_keepalive: db_qa_setup.sh failed with exit code {result.returncode}\n"
            f"  stderr: {stderr_snippet}",
            RuntimeWarning,
            stacklevel=2,
        )

    for _ in range(30):
        if _mariadb_alive():
            return True
        time.sleep(1)
    return False


@pytest.fixture(autouse=True)
def mariadb_keepalive(db):
    """Reinicia MariaDB si cayó antes del test (ADR-008)."""
    if not _mariadb_alive():
        _restart_mariadb()
    yield


# ─── DB Objects — SPs, funciones y vistas (H-DB-01) ─────────────────────────
# Cuando pytest-django recrea practicayoruba_qa, los objetos SQL instalados
# manualmente (SPs, funciones, vistas) desaparecen. Este fixture los reinstala
# automáticamente al inicio de la sesión de tests si no existen.
# Orden OBLIGATORIO por dependencias: funciones → vistas → SPs.

# conftest.py está en tests/ (hijo directo del repo e-commerce-api/).
# e-commerce-db es hermano de e-commerce-api/ en /home/user/.
_REPOS_ROOT  = _REPO_ROOT.parent                          # /home/user
_DB_OBJETOS  = _REPOS_ROOT / 'e-commerce-db' / 'provisioners' / 'mariadb' / 'objetos'

# Orden de instalación: (tipo, nombre_objeto, path_relativo_desde_objetos)
_DB_OBJECTS_ORDERED = [
    # Funciones (sin dependencias entre sí)
    ('function', 'fn_price_with_tax',           'funciones/fn_price_with_tax.sql'),
    ('function', 'fn_qualifies_free_shipping',   'funciones/fn_qualifies_free_shipping.sql'),
    ('function', 'fn_stock_status',              'funciones/fn_stock_status.sql'),
    # Vistas — v_published_catalog primero (otras vistas pueden depender de ella)
    ('view',     'v_published_catalog',          'vistas/v_published_catalog.sql'),
    ('view',     'v_featured_products',          'vistas/v_featured_products.sql'),
    ('view',     'v_low_stock',                  'vistas/v_low_stock.sql'),
    # Stored Procedures
    ('procedure', 'sp_rpt_catalog_by_category',  'sps/sp_rpt_catalog_by_category.sql'),
    ('procedure', 'sp_rpt_catalog_summary',      'sps/sp_rpt_catalog_summary.sql'),
    ('procedure', 'sp_rpt_low_stock',            'sps/sp_rpt_low_stock.sql'),
]


def _db_object_exists(cursor, db_name: str, obj_type: str, obj_name: str) -> bool:
    """Verifica si un SP, función o vista existe en la BD."""
    if obj_type == 'procedure':
        cursor.execute(
            'SHOW PROCEDURE STATUS WHERE Db = %s AND Name = %s',
            [db_name, obj_name],
        )
        return cursor.fetchone() is not None
    elif obj_type == 'function':
        cursor.execute(
            'SHOW FUNCTION STATUS WHERE Db = %s AND Name = %s',
            [db_name, obj_name],
        )
        return cursor.fetchone() is not None
    elif obj_type == 'view':
        cursor.execute(
            'SELECT COUNT(*) FROM information_schema.VIEWS '
            'WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s',
            [db_name, obj_name],
        )
        row = cursor.fetchone()
        return bool(row and row[0])
    return False


def _run_sql_file(sql_path: Path, db_settings: dict) -> bool:
    """
    Ejecuta un archivo SQL usando el cliente mariadb.
    Usa MYSQL_PWD para no exponer la contraseña en la línea de comandos.
    Retorna True si tuvo éxito.
    """
    env = {'MYSQL_PWD': db_settings.get('PASSWORD', '')}

    cmd = ['mariadb', '--batch']

    # Conexión — socket Unix tiene prioridad si está configurado
    unix_socket = db_settings.get('OPTIONS', {}).get('unix_socket', '')
    if unix_socket:
        cmd += [f'--socket={unix_socket}']
    else:
        host = db_settings.get('HOST', '127.0.0.1')
        port = str(db_settings.get('PORT', '3306'))
        cmd += [f'--host={host}', f'--port={port}']

    cmd += [
        f'--user={db_settings.get("USER", "root")}',
        db_settings.get('NAME', ''),
    ]

    try:
        with open(sql_path, 'r', encoding='utf-8') as fh:
            sql_content = fh.read()
        result = subprocess.run(
            cmd,
            input=sql_content.encode('utf-8'),
            capture_output=True,
            timeout=30,
            env={**__import__('os').environ, **env},
        )
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='replace')[:500]
            warnings.warn(
                f'db_objects_setup: error ejecutando {sql_path.name}: {stderr}',
                RuntimeWarning,
                stacklevel=2,
            )
            return False
        return True
    except Exception as exc:
        warnings.warn(
            f'db_objects_setup: excepción ejecutando {sql_path.name}: {exc}',
            RuntimeWarning,
            stacklevel=2,
        )
        return False


@pytest.fixture(scope='session', autouse=True)
def db_objects_setup(django_db_setup, django_db_blocker):
    """
    Instala SPs, funciones y vistas en practicayoruba_qa si no existen.

    H-DB-01: cuando pytest-django recrea la BD con --create-db, los objetos
    SQL instalados manualmente desaparecen. Este fixture los reinstala
    automáticamente al comienzo de cada sesión de tests.

    Orden: funciones → vistas (v_published_catalog primero) → SPs.
    """
    if not _DB_OBJETOS.exists():
        warnings.warn(
            f'db_objects_setup: directorio e-commerce-db no encontrado en '
            f'{_DB_OBJETOS}. Los tests que dependen de SPs/funciones/vistas '
            f'pueden fallar.',
            RuntimeWarning,
            stacklevel=2,
        )
        return

    db_settings = connection.settings_dict
    db_name     = db_settings.get('NAME', '')

    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            for obj_type, obj_name, rel_path in _DB_OBJECTS_ORDERED:
                sql_path = _DB_OBJETOS / rel_path
                if not sql_path.exists():
                    warnings.warn(
                        f'db_objects_setup: SQL no encontrado: {sql_path}',
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    continue

                if _db_object_exists(cursor, db_name, obj_type, obj_name):
                    continue  # ya instalado — no reinstalar

                success = _run_sql_file(sql_path, db_settings)
                if not success:
                    warnings.warn(
                        f'db_objects_setup: falló la instalación de {obj_name} '
                        f'({obj_type}). Tests dependientes pueden fallar.',
                        RuntimeWarning,
                        stacklevel=2,
                    )
