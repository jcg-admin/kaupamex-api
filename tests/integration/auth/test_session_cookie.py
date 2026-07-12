"""Tests de integracion — sesion de servidor como auth unica (ADR-018).

Verifican que el login establece una **sesion de servidor** (cookie HttpOnly)
de modo que la sesion persiste sin ningun token en memoria, y que el endpoint
de estado de sesion la reporta. Cierra el problema del ADR-018: "la sesion se
pierde en cualquier carga completa de pagina". Tras la migracion (Opcion 3) ya
no se emite token CSRF: la defensa CSRF es SameSite=Strict + __Host-.
"""
import pytest

pytestmark = pytest.mark.api

LOGIN_URL = '/api/v2/auth/login/'
SESSION_URL = '/api/v2/auth/session/'
SESSION_LOGOUT_URL = '/api/v2/auth/session/logout/'


class TestSessionStatusAnon:

    def test_anonimo_no_autenticado(self, api_client, db):
        r = api_client.get(SESSION_URL)
        assert r.status_code == 200
        data = r.json()
        assert data['isAuthenticated'] is False
        assert data['user'] is None
        # Ya no se entrega token CSRF (migracion Opcion 3).
        assert 'csrfToken' not in data


class TestSessionEstablecidaEnLogin:

    def test_login_setea_cookie_de_sesion(self, api_client, user):
        r = api_client.post(
            LOGIN_URL,
            {'username': user.email, 'password': 'TestPass123!'},
            format='json',
        )
        assert r.status_code == 200
        # ADR-018: ademas del JWT, se emite la cookie de sesion.
        assert 'sessionid' in r.cookies

    def test_sesion_persiste_sin_token_en_memoria(self, api_client, user):
        # Login establece la sesion (la cookie queda en el jar del cliente).
        api_client.post(
            LOGIN_URL,
            {'username': user.email, 'password': 'TestPass123!'},
            format='json',
        )
        # Simula la recarga: nueva request SIN Authorization, solo la cookie.
        api_client.credentials()  # limpia cualquier header de auth
        r = api_client.get(SESSION_URL)
        assert r.status_code == 200
        data = r.json()
        assert data['isAuthenticated'] is True
        assert data['user']['username'] == user.email


class TestSessionLogout:

    def test_logout_cierra_la_sesion(self, api_client, user):
        api_client.post(
            LOGIN_URL,
            {'username': user.email, 'password': 'TestPass123!'},
            format='json',
        )
        api_client.credentials()
        assert api_client.get(SESSION_URL).json()['isAuthenticated'] is True

        r = api_client.post(SESSION_LOGOUT_URL)
        assert r.status_code == 204

        assert api_client.get(SESSION_URL).json()['isAuthenticated'] is False
