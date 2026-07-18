from django.apps import AppConfig


class AuthzTotpConfig(AppConfig):
    """App de feature opcional: 2FA por TOTP (DEC-01, ~ auth_totp de Odoo).

    Segundo factor de autenticación basado en TOTP (RFC 6238), instalable
    aparte del core de autorización — como ``auth_totp`` en Odoo. El secreto
    vive en ``authz_totp_secret`` (esta app); el gate del segundo paso se
    inyecta en el login (``PYTokenObtainPairSerializer``) tras verificar la
    contraseña. Es el hermano "fuerte" de ``authz_reauth`` (step-up por
    re-contraseña): aquí el factor es un código de un authenticator.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.authz_totp'
    verbose_name = 'Autorización — 2FA (TOTP)'
