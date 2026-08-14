"""AppConfig — addons.authz_ldap (Odoo auth_ldap)."""
from django.apps import AppConfig


class AuthzLdapConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_ldap'
    verbose_name = 'Autenticación — Federación LDAP'
