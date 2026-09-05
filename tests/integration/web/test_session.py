"""Tests de la familia ``web`` — sesión del cliente.

Contrato adaptado de ``odoo19c: addons/web/controllers/session.py``
(``odoo-tools@622ddc2a``). Lo que se verifica es la frontera: quién puede
abrir sesión, qué devuelve al abrirla, y que cerrarla la cierra de verdad.
"""
import pytest

pytestmark = pytest.mark.integration

AUTHENTICATE = '/api/v2/web/session/authenticate/'
SESSION      = '/api/v2/web/session/'
DESTROY      = '/api/v2/web/session/destroy/'
LOGOUT       = '/api/v2/web/session/logout/'


class TestSessionAuthenticate:
    """``/web/session/authenticate`` — ``auth="none"`` en la referencia."""

    def test_valid_credential_opens_session(self, api_client, user):
        r = api_client.post(
            AUTHENTICATE,
            {'login': user.login, 'password': 'TestPass123!'},
            format='json')
        assert r.status_code == 200
        assert r.data['uid'] == user.pk
        assert r.data['login'] == user.login
        # El nombre humano llega delegado del partner (_inherits).
        assert r.data['name'] == user.partner.name

    def test_open_session_is_usable(self, api_client, user):
        """La sesión abierta autentica la siguiente petición.

        Es la verificación que separa "el endpoint responde 200" de "el
        endpoint abre sesión": sin ella, un 200 que no persistiera nada
        pasaría igual.
        """
        api_client.post(
            AUTHENTICATE,
            {'login': user.login, 'password': 'TestPass123!'},
            format='json')
        r = api_client.get(SESSION)
        assert r.status_code == 200
        assert r.data['uid'] == user.pk

    def test_wrong_password_returns_401(self, api_client, user):
        r = api_client.post(
            AUTHENTICATE,
            {'login': user.login, 'password': 'WrongPass999!'},
            format='json')
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'INVALID_CREDENTIAL'

    def test_unknown_login_returns_same_code(self, api_client, db):
        """Mismo código que la contraseña errónea — no revela qué logins existen."""
        r = api_client.post(
            AUTHENTICATE,
            {'login': 'nobody@kaupamex.mx', 'password': 'TestPass123!'},
            format='json')
        assert r.status_code == 401
        assert r.data['codigo_error'] == 'INVALID_CREDENTIAL'

    def test_missing_password_returns_400(self, api_client, db):
        r = api_client.post(
            AUTHENTICATE, {'login': 'a@b.mx'}, format='json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'CREDENTIAL_REQUIRED'

    def test_password_is_not_echoed(self, api_client, user):
        """El serializer declara la contraseña ``write_only``."""
        r = api_client.post(
            AUTHENTICATE,
            {'login': user.login, 'password': 'TestPass123!'},
            format='json')
        assert 'password' not in r.data


class TestSessionInfo:
    """``/web/session/get_session_info`` — ``auth='user'``."""

    def test_unauthenticated_returns_401(self, api_client, db):
        assert api_client.get(SESSION).status_code == 401

    def test_authenticated_returns_identity(self, auth_client, user):
        r = auth_client.get(SESSION)
        assert r.status_code == 200
        assert r.data['uid'] == user.pk
        assert r.data['is_system'] is False


class TestSessionDestroy:
    """``/web/session/destroy`` — ``auth='user'`` en la referencia."""

    def test_unauthenticated_returns_401(self, api_client, db):
        assert api_client.post(DESTROY).status_code == 401

    def test_closes_the_session(self, auth_client):
        assert auth_client.post(DESTROY).status_code == 204
        # La sesión ya no autentica: el 401 es la prueba de que se cerró.
        assert auth_client.get(SESSION).status_code == 401


class TestSessionLogout:
    """``/web/session/logout`` — ``auth='none'``, por tanto idempotente."""

    def test_without_session_returns_204(self, api_client, db):
        assert api_client.post(LOGOUT).status_code == 204

    def test_with_session_closes_it(self, auth_client):
        assert auth_client.post(LOGOUT).status_code == 204
        assert auth_client.get(SESSION).status_code == 401
