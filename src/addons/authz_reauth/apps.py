from django.apps import AppConfig


class AuthzReauthConfig(AppConfig):
    """App de feature opcional: re-autenticación de acciones sensibles (DEC-12).

    Análoga a ``auth_totp`` de Odoo — un módulo instalable aparte que agrega
    step-up sobre el core de autorización (``addons.authz``) sin acoplarlo. Se
    separó del core en SOL-094 frente B (DEC-01): el gate ``assert_session_fresh``
    y la ``ReauthSession`` viven aquí; ``authz`` solo los invoca vía el facade
    ``services``.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_reauth'
    verbose_name = 'Autorización — Re-autenticación (step-up)'
