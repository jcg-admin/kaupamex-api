from django.apps import AppConfig


class AuthzSignupConfig(AppConfig):
    """App de feature opcional: gobierno del auto-registro y reset (DEC-01).

    Adaptación nativa de ``auth_signup`` de Odoo (LGPL-3). Odoo gobierna el
    signup con config-params editables en runtime — ``auth_signup.invitation_scope``
    ('b2c' free / 'b2b' invitation-only) y ``auth_signup.reset_password`` — que
    ``res.users`` consulta antes de crear la cuenta o mandar el reset. Aquí se
    expresa con ``SystemParameter`` (L2) consultado por las vistas públicas de
    ``users`` (``RegisterView`` / ``PasswordResetRequestView``). Así abrir o
    cerrar el registro (o el reset) es editable en caliente, sin redeploy y
    **sin nada cableado** en las vistas.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_signup'
    verbose_name = 'Autorización — Auto-registro y reset'
