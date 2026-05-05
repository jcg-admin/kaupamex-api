"""
Tests de integracion — Cambio de contrasena
UC-AUTH-08: Cambiar Contrasena
"""
import pytest

pytestmark = pytest.mark.integration

CHANGE_URL = '/api/v1/auth/change-password/'


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
