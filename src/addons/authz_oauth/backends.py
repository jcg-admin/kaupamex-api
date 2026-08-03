"""Backend de token OAuth — ≙ ``auth_oauth/models/res_users.py:152-167``.

Adaptación de Odoo ``auth_oauth`` (LGPL-3). La referencia acepta la
credencial ``{'type': 'oauth_token', 'token': ...}`` en ``_check_credentials``
comparando el token contra el ``oauth_access_token`` almacenado — es lo que
usa su controlador tras ``auth_oauth()`` para abrir la sesión.

Aquí igual: la vista de signin valida el token contra el proveedor
(``models.res_users.auth_oauth``) y después autentica por esta vía. Se
cablea al final de ``AUTHENTICATION_BACKENDS`` — el kwarg ``oauth_token``
hace que los backends de password lo ignoren, y este backend ignora los
logins con password (mismo aislamiento que el ``credential['type']`` de la
referencia).
"""
from django.apps import apps as django_apps
from django.contrib.auth.backends import BaseBackend

from addons.authz_oauth.models.res_users import OauthAccount


class OauthTokenBackend(BaseBackend):

    def authenticate(self, request, oauth_token=None, **kwargs):
        if not oauth_token:
            return None
        account = (
            OauthAccount.objects
            .select_related('user')
            .filter(oauth_access_token=oauth_token, user__active=True)
            .first()
        )
        return account.user if account else None

    def get_user(self, user_id):
        ResUsers = django_apps.get_model('base', 'ResUsers')
        return ResUsers.objects.filter(pk=user_id, active=True).first()
