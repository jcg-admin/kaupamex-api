"""AppConfig — addons.authz_totp_mail (Odoo auth_totp_mail)."""
import importlib

from django.apps import AppConfig


class AuthzTotpMailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_totp_mail'
    verbose_name = 'Autenticación — 2FA por correo e invitación'

    #: Extensiones que este addon cuelga de modelos ajenos — ≙ ``_inherit``.
    _EXTENSIONS = {
        'addons.authz_totp_mail.models.res_users':
            'apply_authz_totp_mail_res_users_extensions',
    }

    def ready(self):
        # Excepción #4 de no-lazy-imports: registro de signals en ready()
        # via importlib (llamada, no statement). Las señales replican el
        # write-hook de la referencia sobre totp_secret (activar/desactivar
        # 2FA → notificación de seguridad).
        importlib.import_module('addons.authz_totp_mail.models.signals')
        # El eslabón externo de la cadena de MFA. Va después del de
        # authz_totp por el orden de INSTALLED_APPS, que es lo que hace que
        # keep_previous le dé la precedencia al interno.
        for module_path, function_name in self._EXTENSIONS.items():
            getattr(importlib.import_module(module_path), function_name)()
