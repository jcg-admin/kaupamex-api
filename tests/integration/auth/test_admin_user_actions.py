"""
Tests de integracion — Acciones admin sobre usuarios
UC-AUTH-12 (ver perfil), UC-AUTH-13 (suspender),
UC-AUTH-14 (reactivar), UC-AUTH-15 (crear admin)
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.integration

USERS_URL = '/api/v1/admin/users/'


@pytest.fixture
def target_user(db):
    return get_user_model().objects.create_user(
        username='targetuser', email='target@test.mx',
        password='Pass123!', is_active=True,
    )


class TestAdminUserDetail:

    def test_admin_puede_ver_perfil_de_usuario(self, admin_auth_client, target_user, db):
        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 200

    def test_comprador_no_puede_ver_perfil_de_usuario(self, auth_client, target_user, db):
        r = auth_client.get(f'{USERS_URL}{target_user.pk}/')
        assert r.status_code == 403

    def test_perfil_contiene_campos_esperados(self, admin_auth_client, target_user, db):
        r = admin_auth_client.get(f'{USERS_URL}{target_user.pk}/')
        data = r.json()
        for field in ['id', 'username', 'email', 'is_active', 'is_staff', 'date_joined']:
            assert field in data

    def test_usuario_inexistente_retorna_404(self, admin_auth_client, db):
        r = admin_auth_client.get(f'{USERS_URL}99999/')
        assert r.status_code == 404


class TestAdminSuspendUser:

    def test_suspender_usuario_retorna_200(self, admin_auth_client, target_user, db):
        r = admin_auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        assert r.status_code == 200

    def test_suspender_establece_is_active_false(self, admin_auth_client, target_user, db):
        admin_auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        target_user.refresh_from_db()
        assert target_user.is_active is False

    def test_suspender_invalida_sesiones(self, admin_auth_client, target_user, db, api_client):
        refresh = str(RefreshToken.for_user(target_user))
        admin_auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        r = api_client.post('/api/v1/auth/refresh/', {'refresh': refresh}, format='json')
        assert r.status_code == 401

    def test_comprador_no_puede_suspender(self, auth_client, target_user, db):
        r = auth_client.post(f'{USERS_URL}{target_user.pk}/suspend/')
        assert r.status_code == 403

    def test_admin_no_puede_suspenderse_a_si_mismo(self, admin_auth_client, admin_user, db):
        r = admin_auth_client.post(f'{USERS_URL}{admin_user.pk}/suspend/')
        assert r.status_code == 400


class TestAdminReactivateUser:

    @pytest.fixture
    def inactive_target(self, db):
        return get_user_model().objects.create_user(
            username='inactiveuser', email='inactive@test.mx',
            password='Pass123!', is_active=False,
        )

    def test_reactivar_retorna_200(self, admin_auth_client, inactive_target, db):
        r = admin_auth_client.post(f'{USERS_URL}{inactive_target.pk}/reactivate/')
        assert r.status_code == 200

    def test_reactivar_establece_is_active_true(self, admin_auth_client, inactive_target, db):
        admin_auth_client.post(f'{USERS_URL}{inactive_target.pk}/reactivate/')
        inactive_target.refresh_from_db()
        assert inactive_target.is_active is True

    def test_comprador_no_puede_reactivar(self, auth_client, inactive_target, db):
        r = auth_client.post(f'{USERS_URL}{inactive_target.pk}/reactivate/')
        assert r.status_code == 403


class TestAdminCreateAdmin:

    def test_crear_admin_retorna_201(self, admin_auth_client, db):
        r = admin_auth_client.post(USERS_URL, {
            'username': 'newadmin',
            'email': 'newadmin@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        assert r.status_code == 201

    def test_nuevo_admin_tiene_is_staff_true(self, admin_auth_client, db):
        admin_auth_client.post(USERS_URL, {
            'username': 'newadmin2',
            'email': 'newadmin2@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        user = get_user_model().objects.get(username='newadmin2')
        assert user.is_staff is True

    def test_nuevo_admin_esta_activo(self, admin_auth_client, db):
        admin_auth_client.post(USERS_URL, {
            'username': 'newadmin3',
            'email': 'newadmin3@test.mx',
            'password': 'AdminPass123!',
        }, format='json')
        user = get_user_model().objects.get(username='newadmin3')
        assert user.is_active is True

    def test_comprador_no_puede_crear_admin(self, auth_client, db):
        r = auth_client.post(USERS_URL, {
            'username': 'hackadmin',
            'email': 'hack@test.mx',
            'password': 'HackPass123!',
        }, format='json')
        assert r.status_code == 403
