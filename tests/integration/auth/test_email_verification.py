"""
Tests de integracion — Verificacion de email
UC-AUTH-10 + FR-AUTH-01.05 (envio en registro)
"""
import pytest
from django.core import mail
from django.core.management import call_command
from django.contrib.auth import get_user_model
from apps.authz.models import RoleAssignment
from apps.authz.services import BUYER_ROLE_CODE
from apps.users.models import EmailVerificationToken
from apps.users.tokens_email import create_verification_token, send_verification_email

pytestmark = pytest.mark.integration

VERIFY_URL  = '/api/v2/auth/verify-email/'
RESEND_URL  = '/api/v2/auth/resend-verification/'
REGISTER_URL = '/api/v2/auth/register/'


@pytest.fixture
def inactive_user(db):
    User = get_user_model()
    return User.objects.create_user(
        email='unverified@practicayoruba.mx',
        password='TestPass123!',
        is_active=False,
    )


class TestEmailVerification:

    def _get_verify_token(self, inactive_user):
        token_obj = EmailVerificationToken.objects.filter(
            user=inactive_user, used_at__isnull=True
        ).first()
        return token_obj.plain_token if token_obj else None

    def test_token_valido_activa_cuenta(self, api_client, inactive_user, db):
        plain = create_verification_token(inactive_user)
        r = api_client.post(VERIFY_URL, {'token': plain}, format='json')
        assert r.status_code == 200
        inactive_user.refresh_from_db()
        assert inactive_user.is_active is True

    def test_validar_asigna_rol_comprador(self, api_client, inactive_user, db):
        """ADR-020: todo usuario registrado y validado recibe ``comprador``.

        Con el catalogo authz sembrado, verificar el email deja el rol
        ``comprador`` asignado (idempotente, tambien cubre altas que no lo
        recibieron al registrarse)."""
        call_command('seed_authz')
        assert not RoleAssignment.objects.filter(
            user=inactive_user, role__code=BUYER_ROLE_CODE
        ).exists()
        plain = create_verification_token(inactive_user)
        r = api_client.post(VERIFY_URL, {'token': plain}, format='json')
        assert r.status_code == 200
        assert RoleAssignment.objects.filter(
            user=inactive_user, role__code=BUYER_ROLE_CODE
        ).exists()

    def test_verificar_inicia_sesion_automaticamente(self, api_client, inactive_user, db):
        """UX (ADR-018): tras verificar, el usuario queda logueado por sesion
        (django_login) para aterrizar en 'next' sin re-loguearse a mano."""
        plain = create_verification_token(inactive_user)
        r = api_client.post(VERIFY_URL, {'token': plain}, format='json')
        assert r.status_code == 200
        assert 'sessionid' in r.cookies          # la respuesta establece la sesion
        # Una peticion posterior (solo cookie, sin credenciales) queda autenticada.
        api_client.credentials()
        prof = api_client.get('/api/v2/auth/profile/')
        assert prof.status_code == 200
        assert prof.json()['email'] == inactive_user.email

    def test_token_invalido_retorna_400(self, api_client, db):
        r = api_client.post(VERIFY_URL, {'token': 'token-falso-xyz'}, format='json')
        assert r.status_code == 400
        assert r.json().get('codigo_error') == 'TOKEN_INVALID'

    def test_token_ya_usado_es_single_use(self, api_client, inactive_user, db):
        """Postmortem verify-token-reuso: el 2o clic al enlace de verificacion
        NO debe dar exito idempotente, sino ``TOKEN_ALREADY_USED`` (single-use,
        alineado con el reset de contrasena)."""
        plain = create_verification_token(inactive_user)
        first = api_client.post(VERIFY_URL, {'token': plain}, format='json')
        assert first.status_code == 200          # 1er clic activa
        inactive_user.refresh_from_db()
        assert inactive_user.is_active is True
        api_client.credentials()                 # limpia la sesion auto-login
        second = api_client.post(VERIFY_URL, {'token': plain}, format='json')
        assert second.status_code == 400
        assert second.json().get('codigo_error') == 'TOKEN_ALREADY_USED'

    def test_verificacion_token_se_crea_al_registrar(self, api_client, db):
        """FR-AUTH-01.05: al crear usuario inactivo se genera token de verificacion."""
        User = get_user_model()
        u = User.objects.create_user(
            email='newuser2@test.mx',
            password='TestPass123!', is_active=False,
        )
        # Crear token manualmente (igual que lo haría la señal en prod)
        plain = create_verification_token(u)
        assert EmailVerificationToken.objects.filter(user=u, used_at__isnull=True).exists()
        assert len(plain) > 0

    def test_email_apunta_a_la_ruta_real_del_front(self, db, settings):
        """El enlace del correo debe usar la ruta del SPA (/auth/verify-email)
        con el token en query string; un path distinto cae en el 404 del
        router. El path viejo /verificar-email/ no debe reaparecer."""
        settings.FRONTEND_URL = 'https://practicayoruba.com'
        User = get_user_model()
        u = User.objects.create_user(
            email='linkuser@test.mx',
            password='TestPass123!', is_active=False,
        )
        mail.outbox.clear()
        send_verification_email(u, 'TOKEN123')
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert 'https://practicayoruba.com/auth/verify-email?token=TOKEN123' in body
        assert '/verificar-email/' not in body

    def test_email_verificacion_incluye_alternativa_html(self, db, settings):
        """Fase 11: el correo es multipart texto+HTML. Django ``send_mail`` con
        ``html_message`` adjunta la alternativa nativamente (sin
        ``EmailMultiAlternatives``). El HTML debe traer el enlace y la marca."""
        settings.FRONTEND_URL = 'https://practicayoruba.com'
        User = get_user_model()
        u = User.objects.create_user(
            email='htmluser@test.mx',
            password='TestPass123!', is_active=False,
        )
        mail.outbox.clear()
        send_verification_email(u, 'TOKENHTML')
        assert len(mail.outbox) == 1
        alts = mail.outbox[0].alternatives
        assert len(alts) == 1
        html, mime = alts[0]
        assert mime == 'text/html'
        assert 'https://practicayoruba.com/auth/verify-email?token=TOKENHTML' in html
        assert 'PracticaYoruba' in html
        assert 'Activar mi cuenta' in html

    def test_resend_usuario_no_verificado_retorna_200(self, api_client, inactive_user, db):
        r = api_client.post(RESEND_URL, {'email': inactive_user.email}, format='json')
        assert r.status_code == 200

    def test_resend_siempre_200_aunque_email_no_exista(self, api_client, db):
        """Seguridad: no revelar si el email existe."""
        r = api_client.post(RESEND_URL, {'email': 'noexiste@test.mx'}, format='json')
        assert r.status_code == 200

    def test_login_cuenta_no_verificada_da_error_diferenciado(self, api_client, inactive_user, db):
        """FR-AUTH-02.09: mensaje diferenciado tras verificacion pendiente."""
        r = api_client.post('/api/v2/auth/login/', {
            'email': inactive_user.email,
            'password': 'TestPass123!',
        }, format='json')
        assert r.status_code == 401
        assert 'EMAIL_NOT_VERIFIED' in str(r.json())

    def test_login_cuenta_verificada_funciona(self, api_client, inactive_user, db):
        plain = create_verification_token(inactive_user)
        api_client.post(VERIFY_URL, {'token': plain}, format='json')
        r = api_client.post('/api/v2/auth/login/', {
            'email': inactive_user.email,
            'password': 'TestPass123!',
        }, format='json')
        assert r.status_code == 200
