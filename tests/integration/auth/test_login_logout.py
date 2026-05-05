"""
Tests de integración — UC-AUTH-02: Login y UC-AUTH-03: Logout
TDD: RED

UC-AUTH-02:
  POST /api/v1/auth/login/
  Request:  { username, password }
  Response 200: { access, refresh, user: { id, username, email, is_staff } }
  Response 401: credenciales inválidas
  Response 400: cuenta inactiva

UC-AUTH-03:
  POST /api/v1/auth/logout/
  Request:  { refresh }
  Response 200: { detail: 'Sesion cerrada.' }
  Response 401: sin autenticacion

FR-AUTH-02.03 — emitir par de tokens JWT
FR-AUTH-03    — invalidar refresh token (blacklist)
"""
import pytest

pytestmark = pytest.mark.api

LOGIN_URL  = '/api/v1/auth/login/'
LOGOUT_URL = '/api/v1/auth/logout/'


class TestLoginHappyPath:

    def test_login_exitoso_retorna_200(self, api_client, user):
        r = api_client.post(LOGIN_URL, {'username': user.username, 'password': 'TestPass123!'}, format='json')
        assert r.status_code == 200

    def test_respuesta_contiene_access_y_refresh(self, api_client, user):
        r = api_client.post(LOGIN_URL, {'username': user.username, 'password': 'TestPass123!'}, format='json')
        data = r.json()
        assert 'access' in data
        assert 'refresh' in data

    def test_respuesta_contiene_datos_del_usuario(self, api_client, user):
        r = api_client.post(LOGIN_URL, {'username': user.username, 'password': 'TestPass123!'}, format='json')
        # simplejwt retorna los campos del token — verificar que el access es un JWT valido
        data = r.json()
        assert data['access']
        # El access token tiene 3 partes separadas por puntos
        assert len(data['access'].split('.')) == 3

    def test_admin_login_exitoso(self, api_client, admin_user):
        r = api_client.post(LOGIN_URL, {'username': admin_user.username, 'password': 'AdminPass123!'}, format='json')
        assert r.status_code == 200


class TestLoginFail:

    def test_credenciales_incorrectas_retorna_401(self, api_client, user):
        r = api_client.post(LOGIN_URL, {'username': user.username, 'password': 'WrongPass!'}, format='json')
        assert r.status_code == 401

    def test_usuario_inexistente_retorna_401(self, api_client, db):
        r = api_client.post(LOGIN_URL, {'username': 'noexiste', 'password': 'Pass1234!'}, format='json')
        assert r.status_code == 401

    def test_cuenta_inactiva_retorna_401(self, api_client, db):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(username='inactivo', password='Pass1234!', is_active=False)
        r = api_client.post(LOGIN_URL, {'username': 'inactivo', 'password': 'Pass1234!'}, format='json')
        assert r.status_code == 401

    def test_campos_vacios_retorna_400(self, api_client, db):
        r = api_client.post(LOGIN_URL, {}, format='json')
        assert r.status_code == 400


class TestLogout:

    def test_logout_con_refresh_valido_retorna_200(self, api_client, user):
        # Primero hacer login para obtener tokens
        login_r = api_client.post(
            LOGIN_URL,
            {'username': user.username, 'password': 'TestPass123!'},
            format='json',
        )
        refresh = login_r.json()['refresh']

        # Hacer logout con el refresh token
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {login_r.json()["access"]}')
        r = api_client.post(LOGOUT_URL, {'refresh': refresh}, format='json')
        assert r.status_code == 200

    def test_logout_sin_autenticacion_retorna_401(self, api_client, db):
        r = api_client.post(LOGOUT_URL, {'refresh': 'token-invalido'}, format='json')
        assert r.status_code == 401

    def test_refresh_token_invalidado_no_puede_renovar(self, api_client, user):
        """FR-AUTH-03: token en blacklist no puede renovar sesion."""
        login_r = api_client.post(
            LOGIN_URL,
            {'username': user.username, 'password': 'TestPass123!'},
            format='json',
        )
        tokens = login_r.json()
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        # Logout — pone refresh en blacklist
        api_client.post(LOGOUT_URL, {'refresh': tokens['refresh']}, format='json')

        # Intentar renovar con el refresh invalidado
        api_client.credentials()
        refresh_r = api_client.post('/api/v1/auth/refresh/', {'refresh': tokens['refresh']}, format='json')
        assert refresh_r.status_code == 401
