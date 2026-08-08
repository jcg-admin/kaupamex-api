"""AppConfig — addons.authz_passkey (Odoo auth_passkey)."""
from django.apps import AppConfig


class AuthzPasskeyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_passkey'
    verbose_name = 'Autenticación — Passkeys (WebAuthn)'
