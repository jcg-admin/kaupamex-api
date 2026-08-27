"""Tests — addons.authz_passkey (WebAuthn).

El test de la referencia (``test_passkey_demo.py``, 523 loc) reproduce
respuestas WebAuthn grabadas contra SU rp_id/orígenes — no son portables a
otro dominio. Aquí la capa criptográfica (``_verify_auth`` /
``_verify_registration_options``) se mockea, igual que la capa LDAP/OAuth en
sus tests hermanos, y se cubre el contrato: challenge en sesión, alta y
login, passkey desconocida, aislamiento por dueño y campos no expuestos.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from addons.authz.bootstrap import assign_buyer_role
from addons.authz.services import invalidate_capabilities
from addons.authz_reauth.models import ReauthSession
from addons.authz_passkey.models import PasskeyKey

User = get_user_model()

OPTIONS_URL = '/api/v2/authz/passkey/auth-options/'
SIGNIN_URL = '/api/v2/authz/passkey/signin/'
KEYS_URL = '/api/v2/authz/passkeys/'
REG_OPTIONS_URL = '/api/v2/authz/passkeys/registration-options/'
REGISTER_URL = '/api/v2/authz/passkeys/register/'


@pytest.fixture
def user(db):
    call_command('seed_authz')
    u = User.objects.create_user(login='passkey@kaupamex.mx', password='x')
    assign_buyer_role(u)
    invalidate_capabilities(u.id)
    return u


def _elevar(client, user):
    client.force_authenticate(user)
    # Cubre tanto la sesión aún sin persistir ('') como la que un request
    # previo ya haya materializado (session_key real) — DEC-12 empareja por
    # session_key y el primer POST que escribe en sesión le asigna una clave.
    keys = {'', client.session.session_key or ''}
    for key in keys:
        ReauthSession.objects.update_or_create(
            user_id=user.pk, session_key=key,
            defaults={'started_at': timezone.now(),
                      'expires_at': timezone.now() + timedelta(seconds=900)})


class TestPasskeyLogin:

    def test_auth_options_publica_y_challenge_en_sesion(self, api_client, db):
        resp = api_client.post(OPTIONS_URL)
        assert resp.status_code == 200
        assert 'challenge' in resp.data
        assert api_client.session.get('webauthn_challenge') == \
            resp.data['challenge']

    def test_signin_con_passkey_conocida(self, api_client, user):
        PasskeyKey.objects.create(
            user=user, name='llave', credential_identifier='cred-1',
            public_key='pk', sign_count=3)
        with patch.object(PasskeyKey, '_verify_auth', return_value=4):
            resp = api_client.post(SIGNIN_URL, {
                'webauthn_response': {'id': 'cred-1'},
            }, format='json')
        assert resp.status_code == 200, resp.data
        assert resp.data['login'] == user.login
        key = PasskeyKey.objects.get(credential_identifier='cred-1')
        assert key.sign_count == 4  # el contador avanza (≙ referencia)

    def test_passkey_desconocida_403(self, api_client, db):
        resp = api_client.post(SIGNIN_URL, {
            'webauthn_response': {'id': 'no-existe'},
        }, format='json')
        assert resp.status_code == 403
        assert resp.data['codigo_error'] == 'PASSKEY_ACCESS_DENIED'


class TestPasskeyManagement:

    def test_registro_crea_passkey(self, api_client, user):
        _elevar(api_client, user)
        resp = api_client.post(REG_OPTIONS_URL)
        assert resp.status_code == 200, resp.data
        assert 'challenge' in resp.data
        _elevar(api_client, user)  # cubre la sesión ya materializada

        with patch.object(
            PasskeyKey, '_verify_registration_options',
            return_value={'credential_id': b'cred-bytes',
                          'credential_public_key': b'pk-bytes'},
        ):
            resp = api_client.post(REGISTER_URL, {
                'name': 'Mi laptop',
                'registration': {'id': 'x'},
            }, format='json')
        assert resp.status_code == 201, resp.data
        assert resp.data['name'] == 'Mi laptop'
        # Los campos group_system NO salen por la API.
        assert 'credential_identifier' not in resp.data
        assert 'public_key' not in resp.data
        assert PasskeyKey.objects.filter(user=user).count() == 1

    def test_lista_y_borrado_solo_propios(self, api_client, user, db):
        otro = User.objects.create_user(login='otro-pk@kaupamex.mx')
        ajena = PasskeyKey.objects.create(
            user=otro, name='ajena', credential_identifier='cred-ajena')
        propia = PasskeyKey.objects.create(
            user=user, name='propia', credential_identifier='cred-propia')

        _elevar(api_client, user)
        resp = api_client.get(KEYS_URL)
        assert resp.status_code == 200
        payload = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        assert [k['name'] for k in payload] == ['propia']

        resp = api_client.delete(f'{KEYS_URL}{ajena.id}/')
        assert resp.status_code == 404  # el queryset acota al dueño
        resp = api_client.delete(f'{KEYS_URL}{propia.id}/')
        assert resp.status_code == 204
        assert not PasskeyKey.objects.filter(user=user).exists()
        assert PasskeyKey.objects.filter(user=otro).exists()

    def test_sin_reauth_fresca_403(self, api_client, user):
        # account.security es sensible: sin ReauthSession, DEC-12 bloquea
        # la mutación (REAUTH_REQUIRED) — el análogo del @check_identity.
        api_client.force_authenticate(user)
        resp = api_client.post(REG_OPTIONS_URL)
        assert resp.status_code == 403
        assert resp.data.get('codigo_error') == 'REAUTH_REQUIRED'
