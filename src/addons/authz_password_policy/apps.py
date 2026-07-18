from django.apps import AppConfig


class AuthzPasswordPolicyConfig(AppConfig):
    """App de feature opcional: política de contraseña configurable en caliente.

    Adaptación nativa de ``auth_password_policy`` de Odoo (LGPL-3). Odoo expone
    la política como **config-param editable en runtime**
    (``auth_password_policy.minlength``) y la aplica en ``_set_password`` via
    ``_check_password_policy``; aquí se expresa con la API nativa de Django
    (``AUTH_PASSWORD_VALIDATORS``) leyendo la política de ``SystemParameter``
    (L2, ``ir.config_parameter``). Así la longitud mínima es **editable en
    caliente** (como en Odoo) en vez de cableada en ``settings``.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_password_policy'
    verbose_name = 'Autorización — Política de contraseña'
