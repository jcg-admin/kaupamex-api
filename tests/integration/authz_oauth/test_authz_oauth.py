"""Tests — addons.authz_oauth (federación OAuth2).

La referencia no trae tests de auth_oauth (medido: sin ``tests/`` en
``odoo19c: auth_oauth/``); se cubren aquí los caminos del código leído
completo (``models/res_users.py`` + ``controllers/main.py``): alta federada
al primer signin, re-login del ya ligado (refresca token), alta bloqueada
con signup cerrado, proveedor deshabilitado, y el CRUD admin gateado. La
capa de red (``auth_oauth_rpc``) se mockea — igual que hace el test de
``auth_ldap`` con su capa LDAP.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from addons.authz.models import Capability, Role, RoleAssignment, RoleCapability
from addons.authz.services import invalidate_capabilities
from addons.authz_reauth.models import ReauthSession
from addons.authz_oauth.models import OauthAccount, OauthProvider
from addons.authz_signup.data import SIGNUP_PARAMETERS
from addons.base.models import SystemParameter

User = get_user_model()

SIGNIN_URL = '/api/v2/authz/oauth/signin/'
PUBLIC_URL = '/api/v2/authz/oauth/providers/public/'
ADMIN_URL = '/api/v2/authz/oauth/providers/'

VALIDATION = {'sub': 'uid-123', 'email': 'fede@kaupamex.mx', 'name': 'Fede'}


@pytest.fixture
def provider(db):
    return OauthProvider.objects.create(
        name='Proveedor Test',
        auth_endpoint='https://idp.test/auth',
        validation_endpoint='https://idp.test/userinfo',
        body='Sign in', enabled=True,
    )


@pytest.fixture
def signup_abierto(db):
    key = 'authz.signup_allow_uninvited'
    assert key in SIGNUP_PARAMETERS, list(SIGNUP_PARAMETERS)
    SystemParameter.objects.update_or_create(
        key=key, defaults={'value': '1'})


class TestOauthSignin:

    def test_primer_signin_crea_usuario_y_abre_sesion(
            self, api_client, provider, signup_abierto):
        assert not User.objects.filter(login='fede@kaupamex.mx').exists()
        with patch(
            'addons.authz_oauth.models.res_users.auth_oauth_rpc',
            return_value=dict(VALIDATION),
        ):
            resp = api_client.post(SIGNIN_URL, {
                'provider': provider.id, 'access_token': 'tok-1',
            }, format='json')
        assert resp.status_code == 200, resp.data
        assert resp.data['login'] == 'fede@kaupamex.mx'
        user = User.objects.get(login='fede@kaupamex.mx')
        assert not user.has_usable_password()
        account = OauthAccount.objects.get(user=user)
        assert account.oauth_uid == 'uid-123'
        assert account.oauth_access_token == 'tok-1'

    def test_relogin_refresca_token_sin_duplicar(
            self, api_client, provider, signup_abierto):
        with patch(
            'addons.authz_oauth.models.res_users.auth_oauth_rpc',
            return_value=dict(VALIDATION),
        ):
            api_client.post(SIGNIN_URL, {
                'provider': provider.id, 'access_token': 'tok-1',
            }, format='json')
            resp = api_client.post(SIGNIN_URL, {
                'provider': provider.id, 'access_token': 'tok-2',
            }, format='json')
        assert resp.status_code == 200, resp.data
        assert User.objects.filter(login='fede@kaupamex.mx').count() == 1
        account = OauthAccount.objects.get(oauth_uid='uid-123')
        assert account.oauth_access_token == 'tok-2'

    def test_signup_cerrado_niega_alta(self, api_client, provider, db):
        SystemParameter.objects.update_or_create(
            key='authz.signup_allow_uninvited', defaults={'value': '0'})
        with patch(
            'addons.authz_oauth.models.res_users.auth_oauth_rpc',
            return_value=dict(VALIDATION),
        ):
            resp = api_client.post(SIGNIN_URL, {
                'provider': provider.id, 'access_token': 'tok-1',
            }, format='json')
        assert resp.status_code == 403
        assert resp.data['codigo_error'] == 'OAUTH_ACCESS_DENIED'
        assert not User.objects.filter(login='fede@kaupamex.mx').exists()

    def test_proveedor_deshabilitado_403(self, api_client, provider):
        provider.enabled = False
        provider.save(update_fields=['enabled'])
        resp = api_client.post(SIGNIN_URL, {
            'provider': provider.id, 'access_token': 'tok-1',
        }, format='json')
        assert resp.status_code == 403
        assert resp.data['codigo_error'] == 'OAUTH_ACCESS_DENIED'

    def test_error_del_proveedor_502(
            self, api_client, provider, signup_abierto):
        with patch(
            'addons.authz_oauth.models.res_users.auth_oauth_rpc',
            return_value={'error': 'invalid_token'},
        ):
            resp = api_client.post(SIGNIN_URL, {
                'provider': provider.id, 'access_token': 'tok-x',
            }, format='json')
        assert resp.status_code == 502
        assert resp.data['codigo_error'] == 'OAUTH_PROVIDER_ERROR'


class TestOauthProviders:

    def test_public_lista_solo_habilitados(self, api_client, provider, db):
        OauthProvider.objects.create(
            name='Apagado', auth_endpoint='https://x/auth',
            validation_endpoint='https://x/u', body='X', enabled=False)
        resp = api_client.get(PUBLIC_URL)
        assert resp.status_code == 200
        names = [p['name'] for p in resp.data]
        assert names == ['Proveedor Test']
        assert 'auth_link' in resp.data[0]
        assert 'client_id=' in resp.data[0]['auth_link']

    def test_crud_gateado_por_capacidad(self, api_client, provider, db):
        call_command('seed_authz')
        user = User.objects.create_user(
            login='oauth-admin@kaupamex.mx', password='x')
        resp_sin = None
        api_client.force_authenticate(user)
        resp_sin = api_client.get(ADMIN_URL)
        assert resp_sin.status_code == 403

        cap = Capability.objects.get(code='permissions.oauth')
        role = Role.objects.create(code='r-oauth-admin', name='OAuth admin')
        RoleCapability.objects.create(role=role, capability=cap)
        RoleAssignment.objects.create(user=user, role=role)
        invalidate_capabilities(user.id)
        ReauthSession.objects.update_or_create(
            user_id=user.pk, session_key='',
            defaults={'started_at': timezone.now(),
                      'expires_at': timezone.now() + timedelta(seconds=900)})
        resp_con = api_client.get(ADMIN_URL)
        assert resp_con.status_code == 200, resp_con.data
