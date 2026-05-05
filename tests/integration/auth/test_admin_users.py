"""
Tests de integracion — Listado de usuarios (Admin)
UC-AUTH-11
"""
import pytest

pytestmark = pytest.mark.integration

USERS_URL = '/api/v1/admin/users/'


@pytest.fixture
def sample_users(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = [
        User.objects.create_user(username=f'buyer{i}', email=f'buyer{i}@test.mx',
                                 password='Pass123!', is_active=(i % 2 == 0))
        for i in range(5)
    ]
    return users


class TestAdminUserList:

    def test_admin_puede_listar_usuarios(self, admin_auth_client, sample_users, db):
        r = admin_auth_client.get(USERS_URL)
        assert r.status_code == 200

    def test_comprador_no_puede_listar_usuarios(self, auth_client, db):
        r = auth_client.get(USERS_URL)
        assert r.status_code == 403

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.get(USERS_URL)
        assert r.status_code == 401

    def test_respuesta_paginada(self, admin_auth_client, sample_users, db):
        r = admin_auth_client.get(USERS_URL)
        data = r.json()
        assert 'count' in data
        assert 'results' in data
        assert isinstance(data['results'], list)

    def test_busqueda_por_username(self, admin_auth_client, sample_users, db):
        r = admin_auth_client.get(USERS_URL, {'search': 'buyer0'})
        results = r.json()['results']
        assert any('buyer0' in u['username'] for u in results)

    def test_filtro_is_active(self, admin_auth_client, sample_users, db):
        r = admin_auth_client.get(USERS_URL, {'is_active': 'true'})
        for u in r.json()['results']:
            assert u['is_active'] is True

    def test_campos_retornados(self, admin_auth_client, sample_users, db):
        r = admin_auth_client.get(USERS_URL)
        user = r.json()['results'][0]
        for field in ['id', 'username', 'email', 'is_active', 'is_staff', 'date_joined']:
            assert field in user
