"""
conftest.py — Fixtures globales para PracticaYoruba API tests.
BD: practicayoruba_qa (config.settings.testing)
"""
import pytest


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
