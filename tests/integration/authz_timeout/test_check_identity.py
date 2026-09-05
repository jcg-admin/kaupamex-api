"""Integration — el candado por tiempo sobre la capa HTTP.

Adaptación de ``test_check_identity_exception`` de
``odoo19c: auth_timeout/tests/test_auth_timeout.py:283-305``, más las dos
aserciones de exención que la fuente reparte entre
``controllers/web_home.py`` y ``controllers/auth_passkey_webauthn.py``.

Los dos ejes, y su ancla en la sesión:

- ``lock_timeout`` contra ``create_time`` → **401 SESSION_LOCK_EXPIRED**
  (hace falta volver a entrar).
- ``lock_timeout_inactivity`` contra ``identity-check-next`` → **403
  CHECK_IDENTITY_REQUIRED** (basta confirmar identidad).

Auth por sesión de servidor (``force_login``, ADR-018): el candado vive en la
sesión, así que ``force_authenticate`` —que deja ``session_key=''``— no serviría
para medirlo.

**El caso de control (``test_the_exemption_is_what_lets_it_through``) es el que exige
el sub-patrón D de ``metrica-decide-la-conclusion.md``.** El caso anterior
afirma que una vista exenta pasa con el candado vencido; su verde no distingue
«la exención funciona» de «el candado nunca se activó en esa petición». El
control pone ``check_identity = True`` sobre esa misma vista y comprueba que
**cae**.
"""
import time

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from addons.authz.controllers.main import MyMenuView
from addons.authz.models import Role, RoleAssignment
from addons.authz.services import invalidate_capabilities
from addons.authz_timeout.exceptions import CHECK_IDENTITY_URL
from addons.authz_timeout.models import res_groups as time_lock
from addons.base.models.res_groups import ResGroups

pytestmark = pytest.mark.integration

User = get_user_model()

PASSWORD = 'CandadoTiempo123!'
#: Endpoint NO exento, gateado por ``account.security`` — la capacidad que
#: ``seed_authz`` siembra en todos los roles (DEC-ENF-01).
PROTECTED_URL = '/api/v2/authz/totp/'
#: Endpoint exento — ≙ ``/web/webclient/load_menus`` de la fuente.
EXEMPT_URL = '/api/v2/authz/me/menu/'
#: El endpoint de confirmación, que recibe la credencial.
CONFIRM_URL = '/api/v2/authz/timeout/session/check-identity/'


@pytest.fixture(autouse=True)
def clean_cache():
    """El resolutor de umbrales cachea por conjunto de grupos."""
    time_lock._clear_lock_timeouts_cache()
    yield
    time_lock._clear_lock_timeouts_cache()


@pytest.fixture
def user(db):
    """Usuario CON rol asignado.

    El rol no es decoración: sin él, ``account.security`` no resuelve y
    ``PROTECTED_URL`` devuelve 403 **por capacidad**, indistinguible del 403
    del candado. Una primera versión de este archivo lo omitía y sus casos
    pasaban por la razón equivocada — el sub-patrón D en vivo.
    """
    call_command('seed_authz')
    user = User.objects.create_user(
        login='candado-http@kaupamex.mx', password=PASSWORD,
        name='Candado HTTP')
    role = Role.objects.create(code='candado-tiempo', name='Candado Tiempo')
    call_command('seed_authz')      # siembra account.* en el rol recién creado
    RoleAssignment.objects.create(user=user, role=role)
    invalidate_capabilities(user.id)
    return user


@pytest.fixture
def client(user, client):
    client.force_login(user)
    return client


def _with_threshold(user, **thresholds):
    """Cuelga del usuario un grupo con los umbrales pedidos."""
    group = ResGroups.objects.create(name='candado-de-prueba', **thresholds)
    user.group_ids.add(group)
    time_lock._clear_lock_timeouts_cache()
    return group


def _session(client, **keys):
    session = client.session
    session.update(keys)
    session.save()


# === 1. Sin umbral configurado: el candado no interviene ================

def test_no_threshold_lets_request_through(client):
    assert client.get(PROTECTED_URL).status_code == 200


# === 2. Inactividad vencida → 403 CHECK_IDENTITY_REQUIRED ==============

def test_expired_inactivity_demands_identity_check(client, user):
    """≙ ``:288-293`` de la fuente."""
    _with_threshold(user, lock_timeout_inactivity=15)
    _session(client, **{'identity-check-next': time.time()})

    response = client.get(PROTECTED_URL)

    assert response.status_code == 403
    body = response.json()
    assert body['codigo_error'] == 'CHECK_IDENTITY_REQUIRED'
    assert body['check_identity_url'] == CHECK_IDENTITY_URL
    assert body['auth_methods'] == ['password']


# === 3. Confirmar la identidad reabre el paso ==========================

def test_confirming_with_password_reopens_access(client, user):
    """≙ ``:295-299`` — tras confirmar, la misma petición pasa."""
    _with_threshold(user, lock_timeout_inactivity=15)
    _session(client, **{'identity-check-next': time.time()})
    assert client.get(PROTECTED_URL).status_code == 403

    confirmation = client.post(
        CONFIRM_URL, {'type': 'password', 'password': PASSWORD},
        content_type='application/json')

    assert confirmation.status_code == 200
    assert client.get(PROTECTED_URL).status_code == 200


def test_wrong_password_does_not_confirm(client, user):
    """La fuente no distingue este caso —su ``_check_credentials`` levanta
    ``AccessDenied``—; aquí se sella como 401 con código propio."""
    _with_threshold(user, lock_timeout_inactivity=15)
    _session(client, **{'identity-check-next': time.time()})

    response = client.post(
        CONFIRM_URL, {'type': 'password', 'password': 'no-es-la-buena'},
        content_type='application/json')

    assert response.status_code == 401
    assert response.json()['codigo_error'] == 'CHECK_IDENTITY_FAILED'
    assert client.get(PROTECTED_URL).status_code == 403


# === 4. Umbral absoluto vencido → 401 SESSION_LOCK_EXPIRED =============

def test_expired_absolute_threshold_closes_the_session(client, user):
    """≙ ``:301-305`` — 25 horas sobre un umbral de 24 exigen entrar de nuevo,
    no sólo confirmar."""
    _with_threshold(user, lock_timeout=24 * 60)
    _session(client, create_time=time.time() - 25 * 60 * 60)

    response = client.get(PROTECTED_URL)

    assert response.status_code == 401
    assert response.json()['codigo_error'] == 'SESSION_LOCK_EXPIRED'


# === 5. La exención declarada por la vista =============================

def test_exempt_view_passes_with_the_lock_expired(client, user):
    """≙ ``auth_timeout/controllers/web_home.py`` — el menú es lo que el
    cliente necesita para dibujar la pantalla donde se confirma."""
    _with_threshold(user, lock_timeout_inactivity=15)
    _session(client, **{'identity-check-next': time.time()})

    assert client.get(PROTECTED_URL).status_code == 403      # no exenta
    assert client.get(EXEMPT_URL).status_code == 200          # exenta


def test_the_exemption_is_what_lets_it_through(client, user, monkeypatch):
    """Control del sub-patrón D: con ``check_identity = True`` sobre la MISMA
    vista, la petición **cae**.

    Sin este caso, el verde del anterior no distingue «el atributo exime» de
    «el candado no llegó a evaluarse en esa ruta».
    """
    _with_threshold(user, lock_timeout_inactivity=15)
    _session(client, **{'identity-check-next': time.time()})
    monkeypatch.setattr(MyMenuView, 'check_identity', True)

    assert client.get(EXEMPT_URL).status_code == 403


# === 6. El estado que el diálogo consume ===============================

def test_state_declares_methods_and_pending_second_factor(client, user):
    """≙ el ``t-att-props`` que la fuente pasa a su componente OWL."""
    _with_threshold(user, lock_timeout_inactivity=15)
    _session(client, **{'identity-check-next': time.time()})

    body = client.get(CHECK_IDENTITY_URL).json()

    assert body['login'] == user.login
    assert body['auth_methods'] == ['password']
    assert body['mfa'] is False
