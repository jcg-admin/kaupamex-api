"""Tests — verificación de correo (``POST /api/v2/authz/verify-email/``).

**Forma propia, no un puerto.** Medido sobre ``odoo-tools@622ddc2a``: en todo
``odoo19c:`` no hay una ``@route`` cuyo path contenga ``verify``/``confirm``
fuera de ``/shop/confirmation``, y ``signup_type`` sólo toma ``'signup'`` o
``'reset'`` (``odoo19c: addons/auth_signup/models/res_partner.py:113``). En la
referencia el alta ES la prueba del buzón — el enlace de invitación llega al
correo. Aquí hay además alta self-service, así que la cuenta nace inactiva y
necesita este paso.

Lo que sí se hereda es el **mecanismo**, y estos tests lo ejercitan: token
firmado stateless, un solo uso vía ``signup_cancel``, e invalidación por
``login_date`` al iniciar sesión.

El auto-login tras verificar es decisión vigente
(``analisis-auto-login-verificacion-email``): hacer clic en el enlace prueba
control del buzón, el mismo nivel de confianza que el reset.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core import mail as django_mail

from exceptions import UserError

from addons.authz_signup.data import seed as seed_signup
from addons.authz_signup.models import res_users as su
from addons.authz_signup.models.signup_request import SignupRequest
from addons.base.models.res_partner import ResPartner

User = get_user_model()

VERIFY_URL = '/api/v2/authz/verify-email/'

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded(db):
    seed_signup()


@pytest.fixture
def unverified_user(seeded, db):
    """Cuenta recién dada de alta: inactiva y pendiente de verificar."""
    partner = ResPartner.objects.create(
        name='Sin verificar', email='pending@kaupamex.mx')
    user = User.objects.create_user(
        login='pending@kaupamex.mx', password='Str0ng-Passw0rd!',
        partner=partner)
    user.active = False
    user.deactivated_reason = User.DEACTIVATION_UNVERIFIED
    user.save(update_fields=['active', 'deactivated_reason', 'updated_at'])
    return user


class TestSendVerificationEmail:
    def test_send_enqueues_mail_and_marks_request(self, unverified_user):
        django_mail.outbox.clear()
        token = su.send_verification_email(unverified_user)

        assert token
        assert len(django_mail.outbox) == 1
        assert unverified_user.login in django_mail.outbox[0].to
        request = SignupRequest.objects.get(partner=unverified_user.partner)
        assert request.signup_type == SignupRequest.TYPE_VERIFY

    def test_send_refuses_already_verified_account(self, seeded, db):
        partner = ResPartner.objects.create(
            name='Activa', email='active@kaupamex.mx')
        user = User.objects.create_user(
            login='active@kaupamex.mx', password='Str0ng-Passw0rd!',
            partner=partner)
        with pytest.raises(UserError):
            su.send_verification_email(user)

    def test_send_refuses_admin_suspended_account(self, unverified_user):
        """Reactivar por correo una cuenta suspendida saltaría al admin."""
        unverified_user.deactivated_reason = User.DEACTIVATION_SUSPENDED
        unverified_user.save(update_fields=['deactivated_reason',
                                            'updated_at'])
        with pytest.raises(UserError):
            su.send_verification_email(unverified_user)


class TestVerifyEmailEndpoint:
    def test_valid_token_activates_and_opens_session(
            self, api_client, unverified_user):
        token = su.send_verification_email(unverified_user)

        response = api_client.post(VERIFY_URL, {'token': token},
                                   format='json')

        assert response.status_code == 200
        assert response.data['login'] == unverified_user.login
        unverified_user.refresh_from_db()
        assert unverified_user.active is True
        assert unverified_user.deactivated_reason is None
        # La sesión quedó abierta: una petición posterior sólo con la cookie
        # ya va autenticada.
        follow_up = api_client.get('/api/v2/portal/me/')
        assert follow_up.status_code != 401

    def test_token_is_single_use(self, api_client, unverified_user):
        token = su.send_verification_email(unverified_user)
        assert api_client.post(VERIFY_URL, {'token': token},
                               format='json').status_code == 200

        second = api_client.post(VERIFY_URL, {'token': token}, format='json')

        assert second.status_code == 400
        assert second.data['codigo_error'] == 'VERIFY_INVALID_TOKEN'

    def test_reset_token_cannot_activate_an_account(
            self, api_client, unverified_user):
        """Un token de ``reset`` no debe servir de llave de activación."""
        unverified_user.active = True
        unverified_user.save(update_fields=['active', 'updated_at'])
        token = su.send_reset_password(unverified_user)

        response = api_client.post(VERIFY_URL, {'token': token},
                                   format='json')

        assert response.status_code == 400
        assert response.data['codigo_error'] == 'VERIFY_INVALID_TOKEN'

    def test_empty_payload_returns_400(self, api_client, seeded):
        response = api_client.post(VERIFY_URL, {}, format='json')

        assert response.status_code == 400
        assert response.data['codigo_error'] == 'VERIFY_PAYLOAD_REQUIRED'

    def test_resend_does_not_leak_account_existence(
            self, api_client, unverified_user):
        """Misma respuesta exista o no la cuenta — sin enumeración."""
        django_mail.outbox.clear()
        known = api_client.post(VERIFY_URL, {'login': unverified_user.login},
                                format='json')
        unknown = api_client.post(VERIFY_URL,
                                  {'login': 'nobody@example.com'},
                                  format='json')

        assert known.status_code == unknown.status_code == 200
        # El correo sólo sale para la cuenta real.
        assert len(django_mail.outbox) == 1
