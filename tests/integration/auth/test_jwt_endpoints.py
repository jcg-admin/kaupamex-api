"""
Tests de integracion — Endpoints JWT de autenticacion.

TDD: documentan el contrato de la API de auth antes de agregar logica adicional.

Endpoints cubiertos:
  POST /api/v2/auth/login/
  POST /api/v2/auth/refresh/
  POST /api/v2/auth/logout/

BD: practicayoruba_qa
"""
import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.integration


class TestLoginEndpoint:
    """POST /api/v2/auth/login/ — obtiene access + refresh token."""

    def test_login_con_credenciales_validas_retorna_200(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'email': user.email,
            'password': 'TestPass123!'
        }, format='json')

        assert response.status_code == 200

    def test_login_retorna_access_token(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'email': user.email,
            'password': 'TestPass123!'
        }, format='json')

        assert 'access' in response.data

    def test_login_retorna_refresh_token(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'email': user.email,
            'password': 'TestPass123!'
        }, format='json')

        assert 'refresh' in response.data

    def test_login_con_password_incorrecto_retorna_401(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'email': user.email,
            'password': 'WrongPassword!'
        }, format='json')

        assert response.status_code == 401

    def test_login_con_usuario_inexistente_retorna_401(self, api_client, db):
        url = reverse('users:login')
        response = api_client.post(url, {
            'email': 'noexiste@x.mx',
            'password': 'Pass123!'
        }, format='json')

        assert response.status_code == 401

    def test_login_sin_body_retorna_400(self, api_client):
        url = reverse('users:login')
        response = api_client.post(url, {}, format='json')

        assert response.status_code == 400


class TestRefreshEndpoint:
    """POST /api/v2/auth/refresh/ — renueva el access token."""

    def test_refresh_con_token_valido_retorna_200(self, api_client, user):
        refresh = RefreshToken.for_user(user)

        url = reverse('users:token-refresh')
        response = api_client.post(url, {
            'refresh': str(refresh)
        }, format='json')

        assert response.status_code == 200
        assert 'access' in response.data

    def test_refresh_con_token_invalido_retorna_401(self, api_client):
        url = reverse('users:token-refresh')
        response = api_client.post(url, {
            'refresh': 'token.invalido.aqui'
        }, format='json')

        assert response.status_code == 401


class TestLogoutEndpoint:
    """POST /api/v2/auth/logout/ — invalida el refresh token."""

    def test_logout_con_refresh_valido_retorna_200(self, api_client, user):
        refresh = RefreshToken.for_user(user)

        url = reverse('users:logout')
        response = api_client.post(url, {
            'refresh': str(refresh)
        }, format='json')

        assert response.status_code == 200

    def test_refresh_invalido_despues_de_logout(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        token_str = str(refresh)

        # Logout
        url_logout = reverse('users:logout')
        api_client.post(url_logout, {'refresh': token_str}, format='json')

        # Intentar usar el mismo refresh
        url_refresh = reverse('users:token-refresh')
        response = api_client.post(url_refresh, {'refresh': token_str}, format='json')

        assert response.status_code == 401


class TestRefreshValidatesIsActive:
    """
    POST /api/v2/auth/refresh/ — valida user.is_active (D-26).
    Cierra refresh-validar-user-activo. Antes del fix, un usuario
    suspendido (UC-AUTH-13) o self-deleted (UC-AUTH-16) seguia
    renovando hasta 7 dias (refresh TTL).
    """

    def test_refresh_rechaza_user_inactivo(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        token_str = str(refresh)

        # Suspender al usuario tras login
        user.is_active = False
        user.save(update_fields=['is_active'])

        url = reverse('users:token-refresh')
        response = api_client.post(url, {'refresh': token_str}, format='json')

        assert response.status_code == 401
        assert response.data.get('codigo_error') == 'ACCOUNT_INACTIVE'

    def test_refresh_rechaza_self_deleted(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        token_str = str(refresh)

        user.is_active = False
        user.deactivated_reason = 'self_deleted'
        user.save(update_fields=['is_active', 'deactivated_reason'])

        url = reverse('users:token-refresh')
        response = api_client.post(url, {'refresh': token_str}, format='json')

        assert response.status_code == 401
        assert response.data.get('codigo_error') == 'ACCOUNT_INACTIVE'

    def test_refresh_blacklistea_token_de_user_inactivo(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        token_str = str(refresh)

        user.is_active = False
        user.save(update_fields=['is_active'])

        url = reverse('users:token-refresh')

        # Primer intento: rechazado por is_active=False.
        r1 = api_client.post(url, {'refresh': token_str}, format='json')
        assert r1.status_code == 401

        # Segundo intento con mismo token: debe seguir rechazado
        # (blacklisteado por la primera llamada — anti-replay).
        r2 = api_client.post(url, {'refresh': token_str}, format='json')
        assert r2.status_code == 401

    def test_refresh_exitoso_para_user_activo(self, api_client, user):
        """Regression: happy path sigue funcionando tras el fix."""
        refresh = RefreshToken.for_user(user)

        url = reverse('users:token-refresh')
        response = api_client.post(url, {'refresh': str(refresh)}, format='json')

        assert response.status_code == 200
        assert 'access' in response.data
