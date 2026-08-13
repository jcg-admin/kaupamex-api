"""AppConfig — addons.authz_oauth (Odoo auth_oauth)."""
from django.apps import AppConfig


class AuthzOauthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_oauth'
    verbose_name = 'Autenticación — Federación OAuth2'
