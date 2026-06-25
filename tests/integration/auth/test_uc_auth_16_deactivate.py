"""
Tests de integracion — UC-AUTH-16: Dar de Baja la Propia Cuenta.

POST /api/v2/auth/me/deactivate/
Request:  { password }
Response 200: { message }
Response 400: contrasena incorrecta o payload invalido
Response 401: no autenticado
Response 429: rate limit excedido (>5/hora/usuario)

Cierra el flujo:
- is_active = False
- deactivated_reason = 'self_deleted'
- deactivated_at = now
- refresh tokens invalidados (rest_framework_simplejwt blacklist)
- EmailVerificationToken y PasswordResetToken pendientes marcados como
  used_at = NOW (invalidados).
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.users.models import EmailVerificationToken, PasswordResetToken

pytestmark = pytest.mark.api

URL = '/api/v2/auth/me/deactivate/'


class TestDeactivateHappyPath:
    """Camino feliz: usuario autenticado da de baja su cuenta."""

    def test_baja_exitosa_retorna_200(self, auth_client, user):
        r = auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        assert r.status_code == 200, r.content

    def test_baja_setea_is_active_false(self, auth_client, user):
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        user.refresh_from_db()
        assert user.is_active is False

    def test_baja_registra_reason_self_deleted(self, auth_client, user):
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        user.refresh_from_db()
        assert user.deactivated_reason == 'self_deleted'

    def test_baja_registra_deactivated_at(self, auth_client, user):
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        user.refresh_from_db()
        assert user.deactivated_at is not None

    def test_baja_no_elimina_la_fila(self, auth_client, user):
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        # baja logica: la fila persiste
        assert get_user_model().objects.filter(pk=user.pk).exists()


class TestDeactivateValidacion:
    """Errores 400."""

    def test_password_incorrecto_retorna_400(self, auth_client, user):
        r = auth_client.post(URL, {'password': 'wrong'}, format='json')
        assert r.status_code == 400
        assert 'detail' in r.json()

    def test_password_incorrecto_no_modifica_usuario(self, auth_client, user):
        auth_client.post(URL, {'password': 'wrong'}, format='json')
        user.refresh_from_db()
        assert user.is_active is True
        assert user.deactivated_reason is None

    def test_payload_sin_password_retorna_400(self, auth_client):
        r = auth_client.post(URL, {}, format='json')
        assert r.status_code == 400


class TestDeactivateAutenticacion:
    """Errores 401."""

    def test_sin_autenticacion_retorna_401(self, api_client):
        r = api_client.post(URL, {'password': 'x'}, format='json')
        assert r.status_code == 401


class TestDeactivateSideEffects:
    """Tokens pendientes deben invalidarse en la baja."""

    def test_email_verification_token_pendiente_se_marca_usado(
        self, auth_client, user, db,
    ):
        EmailVerificationToken.objects.create(
            user=user,
            token_hash='a' * 64,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        token = EmailVerificationToken.objects.filter(user=user).latest('created_at')
        assert token.used_at is not None

    def test_password_reset_token_pendiente_se_marca_usado(
        self, auth_client, user, db,
    ):
        PasswordResetToken.objects.create(
            user=user,
            token_hash='b' * 64,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        auth_client.post(URL, {'password': 'TestPass123!'}, format='json')
        token = PasswordResetToken.objects.filter(user=user).latest('created_at')
        assert token.used_at is not None


class TestDeactivateRateLimit:
    """5 intentos/hora — el 6to recibe 429."""

    def test_sexto_intento_consecutivo_retorna_429(self, auth_client, user):
        for _ in range(5):
            auth_client.post(URL, {'password': 'wrong'}, format='json')
        r = auth_client.post(URL, {'password': 'wrong'}, format='json')
        assert r.status_code == 429
