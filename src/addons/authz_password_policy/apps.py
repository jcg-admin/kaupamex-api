"""AppConfig — addons.authz_password_policy (Odoo auth_password_policy)."""
from django.apps import AppConfig


class AuthPasswordPolicyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_password_policy'
    verbose_name = 'Autenticación — Política de contraseña'
