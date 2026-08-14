"""Identidad federada OAuth del usuario + validación del access_token.

Adaptación fiel de Odoo ``auth_oauth/models/res_users.py`` (LGPL-3, 170 loc,
leído completo). La referencia cuelga ``oauth_provider_id``/``oauth_uid``/
``oauth_access_token`` de ``res.users`` con la constraint
``unique(oauth_provider_id, oauth_uid)``; aquí viven en tabla propia
``OauthAccount`` (OneToOne con el usuario — en la referencia un usuario tiene
UN proveedor), mismo patrón que ``authz_totp.TotpSecret``.

Métodos de la referencia → aquí:

- ``_auth_oauth_rpc`` / ``_auth_oauth_validate`` / ``_generate_signup_values``
  / ``_auth_oauth_signin`` / ``auth_oauth`` → funciones de este archivo (en
  la referencia son ``@api.model`` — no llevan estado del recordset).
- ``_check_credentials`` (token almacenado como credencial) →
  ``../backends.py`` (``OauthTokenBackend``).
- ``_compute_has_oauth_access_token`` / ``remove_oauth_access_token`` /
  ``SELF_READABLE_FIELDS`` / ``_get_session_token_fields`` → NO portados:
  sirven a la UI de usuarios y a la rotación de session token de Odoo; el
  primero que tenga consumidor aquí se porta con él.
"""
import json
import logging

from django.apps import apps as django_apps
from django.conf import settings

import requests

import fields
import models
from exceptions import AccessDenied, UserError

from addons.authz_oauth.models.oauth_provider import OauthProvider
from addons.authz_signup.models.policy import signup_open
from addons.base.models import SystemParameter, TimeStampedModel

_logger = logging.getLogger(__name__)

# ≙ ir.config_parameter 'auth_oauth.authorization_header' (res_users.py:48);
# renombrado al namespace del addon nuestro.
PARAM_AUTHORIZATION_HEADER = 'authz_oauth.authorization_header'


class OauthAccount(TimeStampedModel):
    """La liga usuario ↔ proveedor. ≙ los campos de ``res_users.py:22-30``."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='oauth_account', verbose_name='Usuario',
    )
    provider = fields.Many2one(
        'authz_oauth.OauthProvider', on_delete=models.CASCADE,
        related_name='accounts', verbose_name='Proveedor OAuth',
    )
    oauth_uid = fields.Char(
        max_length=255, verbose_name='OAuth User ID',
        help_text='user_id del proveedor OAuth.',
    )
    oauth_access_token = fields.Char(
        max_length=2048, blank=True, default='',
        verbose_name='Access token OAuth',
        help_text='NO se expone por la API (NO_ACCESS en la referencia).',
    )

    class Meta:
        db_table = 'authz_oauth_account'
        verbose_name = 'Cuenta OAuth'
        verbose_name_plural = 'Cuentas OAuth'
        constraints = [
            # ≙ _uniq_users_oauth_provider_oauth_uid (res_users.py:27-30)
            models.UniqueConstraint(
                fields=['provider', 'oauth_uid'],
                name='uniq_oauth_provider_oauth_uid',
            ),
        ]

    def __str__(self):
        return f'OauthAccount[{self.user_id}] provider={self.provider_id}'


def _parse_bearer_challenge(header):
    """Extrae los pares del challenge ``WWW-Authenticate: Bearer ...``.

    La referencia usa ``werkzeug.datastructures.WWWAuthenticate`` (su runtime
    lo trae); aquí Django no lo provee y no se agrega una dependencia por un
    header: parse mínimo de la gramática ``k="v"`` del RFC 6750 §3.
    """
    if not header or not header.lower().startswith('bearer'):
        return {}
    out = {}
    for part in header[len('bearer'):].split(','):
        if '=' in part:
            k, _, v = part.partition('=')
            out[k.strip()] = v.strip().strip('"')
    return out


def auth_oauth_rpc(endpoint, access_token):
    """≙ ``_auth_oauth_rpc`` (res_users.py:47-60)."""
    if SystemParameter.get_param(PARAM_AUTHORIZATION_HEADER, ''):
        response = requests.get(
            endpoint, headers={'Authorization': 'Bearer %s' % access_token},
            timeout=10)
    else:
        response = requests.get(
            endpoint, params={'access_token': access_token}, timeout=10)

    if response.ok:  # nb: could be a successful failure
        return response.json()

    auth_challenge = _parse_bearer_challenge(
        response.headers.get('WWW-Authenticate'))
    if auth_challenge and 'error' in auth_challenge:
        return auth_challenge

    return {'error': 'invalid_request'}


def auth_oauth_validate(provider_id, access_token):
    """≙ ``_auth_oauth_validate`` (res_users.py:62-87): devuelve los datos de
    validación del token, con la clave de sujeto unificada en ``user_id``."""
    oauth_provider = OauthProvider.objects.get(pk=provider_id)
    validation = auth_oauth_rpc(
        oauth_provider.validation_endpoint, access_token)
    if validation.get('error'):
        raise UserError(validation['error'])
    if oauth_provider.data_endpoint:
        data = auth_oauth_rpc(oauth_provider.data_endpoint, access_token)
        validation.update(data)
    # unify subject key — mismo orden que la referencia: sub (estándar), id
    # (google v1 / facebook opengraph), user_id (google tokeninfo).
    subject = next(filter(None, [
        validation.pop(key, None)
        for key in ['sub', 'id', 'user_id']
    ]), None)
    if not subject:
        raise AccessDenied('Missing subject identity')
    validation['user_id'] = subject
    return validation


def generate_signup_values(provider_id, validation, params):
    """≙ ``_generate_signup_values`` (res_users.py:89-102)."""
    oauth_uid = validation['user_id']
    email = validation.get(
        'email', 'provider_%s_user_%s' % (provider_id, oauth_uid))
    name = validation.get('name', email)
    return {
        'name': name,
        'login': email,
        'email': email,
        'oauth_provider_id': provider_id,
        'oauth_uid': oauth_uid,
        'oauth_access_token': params['access_token'],
        'active': True,
    }


def auth_oauth_signin(provider_id, validation, params):
    """≙ ``_auth_oauth_signin`` (res_users.py:104-133): recupera (o da de
    alta) al usuario del proveedor+uid validados y devuelve su login.

    El alta federada respeta la política de ``authz_signup`` — la referencia
    llama a ``self.signup(values, token)`` de ``auth_signup``; aquí el gate
    equivalente es ``signup_open()``.
    """
    oauth_uid = str(validation['user_id'])
    account = (
        OauthAccount.objects
        .select_related('user')
        .filter(oauth_uid=oauth_uid, provider_id=provider_id)
        .first()
    )
    if account is not None:
        account.oauth_access_token = params['access_token']
        account.save(update_fields=['oauth_access_token', 'updated_at'])
        return account.user.login

    if params.get('no_user_creation') or not signup_open():
        raise AccessDenied(
            'OAuth signin failed and signup is not allowed')

    values = generate_signup_values(provider_id, validation, params)
    ResUsers = django_apps.get_model('base', 'ResUsers')
    user = ResUsers.objects.create_user(
        login=values['login'], name=values['name'],
    )
    # La credencial vive en el proveedor: sin password local usable.
    user.set_unusable_password()
    user.save(update_fields=['password'])
    OauthAccount.objects.create(
        user=user, provider_id=provider_id, oauth_uid=oauth_uid,
        oauth_access_token=values['oauth_access_token'],
    )
    return user.login


def auth_oauth(provider_id, params):
    """≙ ``auth_oauth`` (res_users.py:135-150): valida el token y firma al
    usuario. Devuelve ``(login, access_token)`` — la referencia antepone el
    dbname porque su sesión es multi-BD; aquí no aplica."""
    access_token = params.get('access_token')
    validation = auth_oauth_validate(provider_id, access_token)
    login = auth_oauth_signin(provider_id, validation, params)
    if not login:
        raise AccessDenied('OAuth signin returned no login')
    return (login, access_token)
