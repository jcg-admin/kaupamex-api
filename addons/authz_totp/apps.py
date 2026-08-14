"""AppConfig — addons.authz_totp (Odoo auth_totp)."""
from django.apps import AppConfig


class AuthTotpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_totp'
    verbose_name = 'Autenticación — 2FA (TOTP)'
