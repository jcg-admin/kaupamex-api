"""AppConfig — addons.auth_signup (Odoo auth_signup)."""
from django.apps import AppConfig


class AuthSignupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.auth_signup'
    verbose_name = 'Autenticación — Auto-registro y reset'
