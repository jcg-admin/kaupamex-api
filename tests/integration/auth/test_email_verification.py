"""
Tests de integracion — Verificacion de email
UC-AUTH-10 + FR-AUTH-01.05 (envio en registro)
"""
import pytest
from django.core import mail

pytestmark = pytest.mark.integration

VERIFY_URL  = '/api/v1/auth/verify-email/'
RESEND_URL  = '/api/v1/auth/resend-verification/'
REGISTER_URL = '/api/v1/auth/register/'


@pytest.fixture
def inactive_user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username='unverifuser',
        email='unverified@practicayoruba.mx',
        password='TestPass123!',
        is_active=False,
    )


class TestEmailVerification:

    def _get_verify_token(self, inactive_user):
        from apps.users.models import EmailVerificationToken
        token_obj = EmailVerificationToken.objects.filter(
            user=inactive_user, used_at__isnull=True
        ).first()
        return token_obj.plain_token if token_obj else None

    def test_token_valido_activa_cuenta(self, api_client, inactive_user, db):
        from apps.users.tokens_email import create_verification_token
        plain = create_verification_token(inactive_user)
        r = api_client.post(VERIFY_URL, {'token': plain}, format='json')
        assert r.status_code == 200
        inactive_user.refresh_from_db()
        assert inactive_user.is_active is True

    def test_token_invalido_retorna_400(self, api_client, db):
        r = api_client.post(VERIFY_URL, {'token': 'token-falso-xyz'}, format='json')
        assert r.status_code == 400

    def test_token_ya_usado_retorna_200_idempotente(self, api_client, inactive_user, db):
        """FR-AUTH-10.02: si la cuenta ya esta activa, 200 (idempotente)."""
        from apps.users.tokens_email import create_verification_token
        plain = create_verification_token(inactive_user)
        api_client.post(VERIFY_URL, {'token': plain}, format='json')
        inactive_user.refresh_from_db()
        r = api_client.post(VERIFY_URL, {'token': plain}, format='json')
        assert r.status_code == 200

    def test_registro_envia_email_verificacion(self, api_client, db):
        """FR-AUTH-01.05: al registrarse se envia email de verificacion."""
        api_client.post(REGISTER_URL, {
            'username': 'newuser',
            'email': 'newuser@practicayoruba.mx',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
        }, format='json')
        assert len(mail.outbox) >= 1
        subjects = [m.subject for m in mail.outbox]
        assert any('verif' in s.lower() or 'activ' in s.lower() for s in subjects)

    def test_resend_usuario_no_verificado_retorna_200(self, api_client, inactive_user, db):
        r = api_client.post(RESEND_URL, {'email': inactive_user.email}, format='json')
        assert r.status_code == 200

    def test_resend_siempre_200_aunque_email_no_exista(self, api_client, db):
        """Seguridad: no revelar si el email existe."""
        r = api_client.post(RESEND_URL, {'email': 'noexiste@test.mx'}, format='json')
        assert r.status_code == 200

    def test_login_cuenta_no_verificada_da_error_diferenciado(self, api_client, inactive_user, db):
        """FR-AUTH-02.09: mensaje diferenciado tras verificacion pendiente."""
        r = api_client.post('/api/v1/auth/login/', {
            'username': inactive_user.username,
            'password': 'TestPass123!',
        }, format='json')
        assert r.status_code == 401
        assert 'EMAIL_NO_VERIFICADO' in str(r.json())

    def test_login_cuenta_verificada_funciona(self, api_client, inactive_user, db):
        from apps.users.tokens_email import create_verification_token
        plain = create_verification_token(inactive_user)
        api_client.post(VERIFY_URL, {'token': plain}, format='json')
        r = api_client.post('/api/v1/auth/login/', {
            'username': inactive_user.username,
            'password': 'TestPass123!',
        }, format='json')
        assert r.status_code == 200
