"""
Tests de integracion — Cambio de contrasena
UC-AUTH-08: Cambiar Contrasena
"""
import pytest
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.integration

CHANGE_URL = '/api/v1/auth/change-password/'
REFRESH_URL = '/api/v1/auth/refresh/'


class TestChangePassword:

    def test_cambio_exitoso_retorna_200(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200

    def test_contrasena_actual_incorrecta_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'PasswordIncorrecta!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 400

    def test_nueva_igual_a_actual_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'TestPass123!',
            'new_password_confirm': 'TestPass123!',
        }, format='json')
        assert r.status_code == 400

    def test_confirmacion_no_coincide_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'Diferente789#',
        }, format='json')
        assert r.status_code == 400

    def test_nueva_contrasena_demasiado_corta_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'corta',
            'new_password_confirm': 'corta',
        }, format='json')
        assert r.status_code == 400

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 401

    def test_nueva_contrasena_persiste(self, auth_client, user, db):
        auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        user.refresh_from_db()
        assert user.check_password('NuevoPass456@')

    def test_contrasena_antigua_ya_no_funciona(self, auth_client, user, db):
        auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        user.refresh_from_db()
        assert not user.check_password('TestPass123!')

    def test_change_password_invalida_sesiones_activas(
        self, auth_client, user, api_client, db,
    ):
        """UC-AUTH-08 PARTE 8.2 (DEC-AUM-01): tras change-password,
        los refresh tokens previos quedan blacklisted. Vector
        account-takeover post-password-change cerrado."""
        # Crear 2 refresh tokens activos para el user (sesiones
        # distintas en multiples dispositivos).
        refresh_a = str(RefreshToken.for_user(user))
        refresh_b = str(RefreshToken.for_user(user))
        # Ejecutar change-password.
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200
        # Verificar que AMBOS refresh tokens previos quedan
        # invalidados (blacklisteados) — no pueden renovar.
        for refresh_str in (refresh_a, refresh_b):
            res = api_client.post(
                REFRESH_URL, {'refresh': refresh_str}, format='json',
            )
            assert res.status_code == 401, (
                f'refresh_str debio quedar blacklisted, status {res.status_code}'
            )
