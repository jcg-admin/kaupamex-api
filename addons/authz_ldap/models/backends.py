"""Backend de autenticación LDAP — ≙ ``auth_ldap/models/res_users.py:13-50``.

Adaptación de Odoo ``auth_ldap`` (LGPL-3). La referencia federa colgándose de
la cadena ``super()`` de ``res.users``:

- ``_login`` (res_users.py:13-32): si el login local falla con
  ``AccessDenied`` **y no existe** usuario local con ese login → intenta el
  bind LDAP y crea el usuario (``_get_or_create_user``).
- ``_check_credentials`` (res_users.py:34-50): si el usuario local **existe**
  pero su password local falla (típico: password vacío porque la credencial
  vive en el directorio) → intenta el bind LDAP con su login.

El equivalente nativo de esa cadena es ``AUTHENTICATION_BACKENDS``: el
backend de password local (``ModelBackend``) va primero y éste es el
fallback. Ambos caminos de la referencia colapsan aquí en ``authenticate()``:

- usuario existe y activo → bind LDAP (camino ``_check_credentials``);
- usuario no existe → bind LDAP por cada configuración y alta federada
  (camino ``_login``).

Cablear en settings::

    AUTHENTICATION_BACKENDS = [
        'django.contrib.auth.backends.ModelBackend',
        'addons.authz_ldap.backends.LdapBackend',
    ]
"""
import logging

from django.apps import apps as django_apps
from django.contrib.auth.backends import BaseBackend

from exceptions import AccessDenied

from addons.authz_ldap.models.res_company_ldap import CompanyLdap

_logger = logging.getLogger(__name__)


class LdapBackend(BaseBackend):
    """Federación por directorio. Devuelve ``None`` (nunca levanta) cuando
    LDAP no autentica — el contrato de un backend Django: ``None`` = "yo no
    puedo, que decida el siguiente", que es el ``raise`` re-propagado de la
    referencia."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        # RFC 4513 §6.3.1 — igual que la referencia (_authenticate:147):
        # nunca intentar un bind con password vacío.
        if not username or not password:
            return None

        login = username.lower().strip()
        ResUsers = django_apps.get_model('base', 'ResUsers')
        user = ResUsers.objects.filter(login__iexact=login).first()

        if user is not None:
            # Camino _check_credentials (res_users.py:34-50): usuario local
            # existente cuyo password local no autenticó. Igual que allí,
            # sólo usuarios activos.
            if not user.active:
                return None
            for conf in CompanyLdap.objects._get_ldap_dicts():
                if CompanyLdap._authenticate(conf, user.login, password):
                    return user
            return None

        # Camino _login (res_users.py:13-32): no hay usuario local — bind y,
        # si la configuración lo permite, alta federada.
        for conf in CompanyLdap.objects._get_ldap_dicts():
            entry = CompanyLdap._authenticate(conf, login, password)
            if entry:
                try:
                    uid = CompanyLdap._get_or_create_user(conf, login, entry)
                except AccessDenied:
                    # create_user=False y sin cuenta local → siguiente conf.
                    continue
                return ResUsers.objects.get(pk=uid)
        return None

    def get_user(self, user_id):
        ResUsers = django_apps.get_model('base', 'ResUsers')
        return ResUsers.objects.filter(pk=user_id, active=True).first()
