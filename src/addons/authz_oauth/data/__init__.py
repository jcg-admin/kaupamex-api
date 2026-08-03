"""Datos semilla del addon — equivalente nativo de ``data/auth_oauth_data.xml``.

La referencia siembra 3 proveedores (``noupdate="1"``): Google y Facebook
**deshabilitados** (``enabled`` sin fijar → False) y "Odoo.com Accounts"
habilitado con ``client_id = database.uuid``. El tercero NO se siembra aquí:
es el proveedor de cuentas de la casa Odoo (su ``/auth_oauth/oea``); el
análogo Kaupamex no existe.

También el config-param del transporte del token (``authorization_header``,
``res_users.py:48``), sembrado vacío = query-param, como el default efectivo
de la referencia (``get_param`` sin default → falsy).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.authz_oauth.models.oauth_provider import OauthProvider
from addons.base.models import SystemParameter

OAUTH_PARAMETERS = {
    'authz_oauth.authorization_header': '',
}

# (name, auth_endpoint, scope, validation_endpoint, data_endpoint,
#  css_class, body) — verbatim del XML de la referencia.
OAUTH_PROVIDERS = [
    {
        'name': 'Google OAuth2',
        'auth_endpoint': 'https://accounts.google.com/o/oauth2/auth',
        'scope': 'openid profile email',
        'validation_endpoint': 'https://www.googleapis.com/oauth2/v3/userinfo',
        'data_endpoint': '',
        'css_class': 'o_auth_oauth_provider_icon o_google_provider',
        'body': 'Sign in with Google',
    },
    {
        'name': 'Facebook Graph',
        'auth_endpoint': 'https://www.facebook.com/dialog/oauth',
        'scope': 'public_profile,email',
        'validation_endpoint': 'https://graph.facebook.com/me',
        'data_endpoint': 'https://graph.facebook.com/me?fields=id,name,email',
        'css_class': 'o_auth_oauth_provider_icon o_facebook_provider',
        'body': 'Sign in with Facebook',
    },
]


def seed(using=DEFAULT_DB_ALIAS):
    """Crea lo ausente. Idempotente y ``noupdate``: nunca pisa lo existente."""
    for key, value in OAUTH_PARAMETERS.items():
        if not SystemParameter.objects.using(using).filter(key=key).exists():
            SystemParameter.objects.using(using).create(key=key, value=value)
    for spec in OAUTH_PROVIDERS:
        if not OauthProvider.objects.using(using).filter(
                name=spec['name']).exists():
            OauthProvider.objects.using(using).create(**spec)
