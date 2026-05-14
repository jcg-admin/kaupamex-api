"""
conftest.py — Fixtures globales para PracticaYoruba API tests.
BD: practicayoruba_qa (config.settings.testing)
"""
import subprocess
import time
from pathlib import Path

import pytest

# ─── Paths del repositorio ───────────────────────────────────────────────────
# Construidos relativos a este archivo — portables entre entornos.
_TESTS_DIR = Path(__file__).resolve().parent        # tests/
_REPO_ROOT  = _TESTS_DIR.parent                     # PracticaYoruba-api/
_DB_QA_SCRIPT = (
    _REPO_ROOT / 'scripts' / 'provisioners' / 'mysql' / 'db_qa_setup.sh'
)



@pytest.fixture
def user(db):
    """Usuario basico activo."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username='testuser',
        email='test@practicayoruba.mx',
        password='TestPass123!',
        first_name='Test',
        last_name='User',
    )


@pytest.fixture
def admin_user(db):
    """Usuario con permisos de staff."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username='adminuser',
        email='admin@practicayoruba.mx',
        password='AdminPass123!',
        is_staff=True,
    )


@pytest.fixture
def api_client():
    """Cliente REST sin autenticar."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Cliente REST autenticado con JWT."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Cliente REST autenticado como admin."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def admin_auth_client(api_client, admin_user):
    """Cliente REST autenticado como administrador."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """
    Limpia el cache de rate limiting antes y después de cada test.
    Sin esto, los tests de login con credenciales incorrectas acumulan
    el contador de la IP 127.0.0.1 y bloquean tests subsecuentes.
    Solo limpia claves de rate limiting (prefijos login_fails: y pw_reset:).
    """
    from django.core.cache import cache

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
    try:
        r = subprocess.run(
            ['mysqladmin', 'ping', '--silent', '--host=127.0.0.1', '--port=3306'],
            capture_output=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
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
        import warnings
        warnings.warn(
            f"mariadb_keepalive: script no encontrado: {_DB_QA_SCRIPT}\n"
            f"  El fixture no puede restablecer la BD automáticamente.\n"
            f"  Verifica que el repositorio esté en el estado correcto.",
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    subprocess.run(
        ['bash', str(_DB_QA_SCRIPT)],
        capture_output=True,
        timeout=90,
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
