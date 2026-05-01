"""
Tests de integracion — Endpoints JWT de autenticacion.

TDD: documentan el contrato de la API de auth antes de agregar logica adicional.

Endpoints cubiertos:
  POST /api/v1/auth/login/
  POST /api/v1/auth/refresh/
  POST /api/v1/auth/logout/

BD: practicayoruba_uta
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.integration


class TestLoginEndpoint:
    """POST /api/v1/auth/login/ — obtiene access + refresh token."""

    def test_login_con_credenciales_validas_retorna_200(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'username': user.username,
            'password': 'TestPass123!'
        }, format='json')

        assert response.status_code == 200

    def test_login_retorna_access_token(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'username': user.username,
            'password': 'TestPass123!'
        }, format='json')

        assert 'access' in response.data

    def test_login_retorna_refresh_token(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'username': user.username,
            'password': 'TestPass123!'
        }, format='json')

        assert 'refresh' in response.data

    def test_login_con_password_incorrecto_retorna_401(self, api_client, user):
        url = reverse('users:login')
        response = api_client.post(url, {
            'username': user.username,
            'password': 'WrongPassword!'
        }, format='json')

        assert response.status_code == 401

    def test_login_con_usuario_inexistente_retorna_401(self, api_client):
        url = reverse('users:login')
        response = api_client.post(url, {
            'username': 'noexiste',
            'password': 'Pass123!'
        }, format='json')

        assert response.status_code == 401

    def test_login_sin_body_retorna_400(self, api_client):
        url = reverse('users:login')
        response = api_client.post(url, {}, format='json')

        assert response.status_code == 400


class TestRefreshEndpoint:
    """POST /api/v1/auth/refresh/ — renueva el access token."""

    def test_refresh_con_token_valido_retorna_200(self, api_client, user):
        from rest_framework_simplejwt.tokens import RefreshToken
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
    """POST /api/v1/auth/logout/ — invalida el refresh token."""

    def test_logout_con_refresh_valido_retorna_200(self, api_client, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        url = reverse('users:logout')
        response = api_client.post(url, {
            'refresh': str(refresh)
        }, format='json')

        assert response.status_code == 200

    def test_refresh_invalido_despues_de_logout(self, api_client, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        token_str = str(refresh)

        # Logout
        url_logout = reverse('users:logout')
        api_client.post(url_logout, {'refresh': token_str}, format='json')

        # Intentar usar el mismo refresh
        url_refresh = reverse('users:token-refresh')
        response = api_client.post(url_refresh, {'refresh': token_str}, format='json')

        assert response.status_code == 401
