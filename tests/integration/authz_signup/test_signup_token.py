"""Tests — addons.authz_signup, signup-token core.

Porta la intención de ``odoo19c: auth_signup/tests/`` (test_auth_signup.py +
test_reset_password.py, leídos completos): el token invita a un partner sin
usuario y al hacer signup le fija la contraseña; el token se invalida al
iniciar sesión (login_date en el payload) y al cancelar el signup; el reset
manda el correo con el enlace; el alta externa respeta el flag de signup
público. El correo corre síncrono en testing (DISPATCH_EMAIL_SYNC).
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail as django_mail
from django.utils import timezone

from exceptions import UserError

from addons.authz_signup.data import seed as seed_signup
from addons.authz_signup.models import res_partner as pp
from addons.authz_signup.models import res_users as su
from addons.authz_signup.models.signup_request import SignupRequest
from addons.base.models import SystemParameter
from addons.base.models.res_partner import ResPartner

User = get_user_model()

SIGNUP_URL = '/api/v2/authz/signup/'
INFO_URL = '/api/v2/authz/signup-info/'
RESET_URL = '/api/v2/authz/request-reset/'


@pytest.fixture
def seeded(db):
    seed_signup()


@pytest.fixture
def signup_abierto(db):
    SystemParameter.objects.update_or_create(
        key='authz.signup_allow_uninvited', defaults={'value': '1'})


class TestSignupToken:
    """≙ ``_generate_signup_token`` / ``_get_partner_from_token``."""

    def test_token_invita_a_partner_sin_usuario(self, seeded, db):
        partner = ResPartner.objects.create(
            name='Invitado', email='inv@kaupamex.mx')
        pp.signup_prepare(partner)
        token = pp._generate_signup_token(partner)
        assert pp._get_partner_from_token(token) == partner

    def test_token_invalido_devuelve_none(self, seeded, db):
        assert pp._get_partner_from_token('firma.mala.zzz') is None

    def test_token_se_invalida_al_cancelar(self, seeded, db):
        partner = ResPartner.objects.create(
            name='X', email='x@kaupamex.mx')
        pp.signup_prepare(partner)
        token = pp._generate_signup_token(partner)
        pp.signup_cancel(partner)
        # el signup_type ya no coincide → token inválido
        assert pp._get_partner_from_token(token) is None

    def test_token_se_invalida_al_iniciar_sesion(self, seeded, db):
        partner = ResPartner.objects.create(
            name='Y', email='y@kaupamex.mx')
        user = User.objects.create_user(login='y@kaupamex.mx', partner=partner)
        pp.signup_prepare(partner)
        token = pp._generate_signup_token(partner)
        assert pp._get_partner_from_token(token) == partner
        # simular login: last_login cambia → login_date del payload difiere
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        assert pp._get_partner_from_token(token) is None


class TestSignupFlow:
    """≙ ``signup`` (res_users.py:37-85)."""

    def test_set_password_con_token(self, seeded, api_client, db):
        partner = ResPartner.objects.create(
            name='Nuevo', email='nuevo@kaupamex.mx')
        pp.signup_prepare(partner)
        token = pp._generate_signup_token(partner)

        resp = api_client.post(SIGNUP_URL, {
            'token': token, 'password': 'Sup3rSecret!',
        }, format='json')
        assert resp.status_code == 200, resp.data
        user = User.objects.get(login='nuevo@kaupamex.mx')
        assert user.check_password('Sup3rSecret!')
        # el token quedó consumido (SignupRequest borrado)
        assert not SignupRequest.objects.filter(partner=partner).exists()

    def test_signup_info_del_token(self, seeded, api_client, db):
        partner = ResPartner.objects.create(
            name='Info', email='info@kaupamex.mx')
        pp.signup_prepare(partner)
        token = pp._generate_signup_token(partner)
        SystemParameter.set_param('authz.password_minlength', '10')
        resp = api_client.get(INFO_URL, {'token': token})
        assert resp.status_code == 200, resp.data
        assert resp.data['name'] == 'Info'
        assert resp.data['email'] == 'info@kaupamex.mx'
        # Fold de auth_password_policy_signup: la política viaja pre-auth.
        assert resp.data['password_minimum_length'] == 10

    def test_signup_info_token_malo_400(self, seeded, api_client, db):
        resp = api_client.get(INFO_URL, {'token': 'malo'})
        assert resp.status_code == 400
        assert resp.data['codigo_error'] == 'SIGNUP_INVALID_TOKEN'

    def test_alta_externa_bloqueada_si_signup_cerrado(
            self, seeded, api_client, db):
        SystemParameter.objects.update_or_create(
            key='authz.signup_allow_uninvited', defaults={'value': '0'})
        resp = api_client.post(SIGNUP_URL, {
            'login': 'externo@kaupamex.mx', 'password': 'Abc12345!',
        }, format='json')
        # 403 SIGNUP_CLOSED, no 400: el alta cerrada es una **denegación de
        # política**, no un payload malformado (status-codes.md). Hasta
        # api@<este commit> el gate vivía sólo en el modelo
        # (authz_signup/models/res_users.py:89) y el 400 de validación del
        # serializer llegaba primero, así que cerrar el alta no era
        # observable desde el endpoint. La referencia corta en el controller
        # antes de mirar el payload (auth_signup/controllers/main.py:91).
        # Ver H-API-269.
        assert resp.status_code == 403
        assert resp.data['codigo_error'] == 'SIGNUP_CLOSED'

    def test_alta_externa_ok_si_abierto(
            self, seeded, signup_abierto, api_client):
        resp = api_client.post(SIGNUP_URL, {
            'login': 'externo2@kaupamex.mx', 'password': 'Abc12345!',
        }, format='json')
        assert resp.status_code == 200, resp.data
        assert User.objects.filter(login='externo2@kaupamex.mx').exists()


class TestResetPassword:
    """≙ ``reset_password`` / ``_action_reset_password``."""

    def test_reset_manda_correo(self, seeded, api_client, db):
        User.objects.create_user(
            login='reset@kaupamex.mx', password='old')
        assert len(django_mail.outbox) == 0
        resp = api_client.post(RESET_URL, {
            'login': 'reset@kaupamex.mx'}, format='json')
        assert resp.status_code == 202
        assert len(django_mail.outbox) == 1
        assert django_mail.outbox[0].to == ['reset@kaupamex.mx']

    def test_reset_login_desconocido_202_sin_correo(
            self, seeded, api_client, db):
        # No revela si la cuenta existe (enumeración de usuarios).
        resp = api_client.post(RESET_URL, {
            'login': 'noexiste@kaupamex.mx'}, format='json')
        assert resp.status_code == 202
        assert len(django_mail.outbox) == 0
