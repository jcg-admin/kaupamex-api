"""
Tests de integracion — Recuperacion de contrasena
UC-AUTH-09 + DT-S2-03 (invalidacion de sesiones)
"""
import pytest
from django.core import mail

pytestmark = pytest.mark.integration

REQUEST_URL = '/api/v1/auth/password-reset/'
CONFIRM_URL = '/api/v1/auth/password-reset/confirm/'


@pytest.fixture
def active_user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username='resetuser',
        email='reset@practicayoruba.mx',
        password='OriginalPass123!',
        is_active=True,
    )


class TestPasswordResetRequest:

    def test_solicitud_retorna_200_email_existente(self, api_client, active_user, db):
        """FR-AUTH-09.01: siempre 200, aunque el email exista."""
        r = api_client.post(REQUEST_URL, {'email': active_user.email}, format='json')
        assert r.status_code == 200

    def test_solicitud_retorna_200_email_inexistente(self, api_client, db):
        """FR-AUTH-09.01: siempre 200 — no revela si el email existe."""
        r = api_client.post(REQUEST_URL, {'email': 'noexiste@test.mx'}, format='json')
        assert r.status_code == 200

    def test_solicitud_envia_email_cuando_usuario_existe(self, api_client, active_user, db):
        api_client.post(REQUEST_URL, {'email': active_user.email}, format='json')
        assert len(mail.outbox) == 1
        assert active_user.email in mail.outbox[0].to

    def test_solicitud_no_envia_email_cuando_usuario_no_existe(self, api_client, db):
        api_client.post(REQUEST_URL, {'email': 'fantasma@test.mx'}, format='json')
        assert len(mail.outbox) == 0

    def test_solicitud_email_formato_invalido_retorna_400(self, api_client, db):
        r = api_client.post(REQUEST_URL, {'email': 'no-es-email'}, format='json')
        assert r.status_code == 400

    def test_rate_limit_3_solicitudes_por_hora(self, api_client, active_user, db):
        """FR-AUTH-09.01: maximo 3 solicitudes por email en 1 hora."""
        from django.core.cache import cache
        cache.clear()
        for _ in range(3):
            api_client.post(REQUEST_URL, {'email': active_user.email}, format='json')
        r = api_client.post(REQUEST_URL, {'email': active_user.email}, format='json')
        assert r.status_code == 429


class TestPasswordResetConfirm:

    def _get_token(self, api_client, active_user):
        """Solicita el reset y extrae el token del email."""
        api_client.post(REQUEST_URL, {'email': active_user.email}, format='json')
        body = mail.outbox[0].body
        import re
        match = re.search(r'token=([A-Za-z0-9_-]+)', body)
        return match.group(1) if match else None

    def test_confirmacion_exitosa_retorna_200(self, api_client, active_user, db):
        from django.core.cache import cache
        cache.clear()
        token = self._get_token(api_client, active_user)
        r = api_client.post(CONFIRM_URL, {
            'token': token,
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200

    def test_nueva_contrasena_persiste(self, api_client, active_user, db):
        from django.core.cache import cache
        cache.clear()
        token = self._get_token(api_client, active_user)
        api_client.post(CONFIRM_URL, {
            'token': token,
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        active_user.refresh_from_db()
        assert active_user.check_password('NuevoPass456@')

    def test_token_invalido_retorna_400(self, api_client, db):
        r = api_client.post(CONFIRM_URL, {
            'token': 'token-invalido-xyz',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 400

    def test_token_ya_usado_retorna_400(self, api_client, active_user, db):
        from django.core.cache import cache
        cache.clear()
        token = self._get_token(api_client, active_user)
        payload = {
            'token': token,
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }
        api_client.post(CONFIRM_URL, payload, format='json')
        r = api_client.post(CONFIRM_URL, payload, format='json')
        assert r.status_code == 400

    def test_confirmaciones_no_coinciden_retorna_400(self, api_client, active_user, db):
        from django.core.cache import cache
        cache.clear()
        token = self._get_token(api_client, active_user)
        r = api_client.post(CONFIRM_URL, {
            'token': token,
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'Diferente789#',
        }, format='json')
        assert r.status_code == 400

    def test_reset_invalida_sesiones_activas(self, api_client, active_user, db):
        """DT-S2-03: tras el reset, los refresh tokens anteriores son invalidos."""
        from django.core.cache import cache
        from rest_framework_simplejwt.tokens import RefreshToken
        cache.clear()
        # Crear sesion activa
        refresh = RefreshToken.for_user(active_user)
        refresh_str = str(refresh)
        # Ejecutar reset
        token = self._get_token(api_client, active_user)
        api_client.post(CONFIRM_URL, {
            'token': token,
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        # Verificar que el refresh anterior queda en blacklist
        r = api_client.post('/api/v1/auth/refresh/', {'refresh': refresh_str}, format='json')
        assert r.status_code == 401
