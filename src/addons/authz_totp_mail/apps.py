"""AppConfig — addons.authz_totp_mail (Odoo auth_totp_mail)."""
import importlib

from django.apps import AppConfig


class AuthzTotpMailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_totp_mail'
    verbose_name = 'Autenticación — 2FA por correo e invitación'

    def ready(self):
        # Excepción #4 de no-lazy-imports: registro de signals en ready()
        # via importlib (llamada, no statement). Las señales replican el
        # write-hook de la referencia sobre totp_secret (activar/desactivar
        # 2FA → notificación de seguridad).
        importlib.import_module('addons.authz_totp_mail.signals')
