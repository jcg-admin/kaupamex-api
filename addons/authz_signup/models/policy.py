"""Política de auto-registro / reset configurable en caliente — authz_signup.

Adaptado de ``auth_signup/models/res_users.py`` de Odoo (LGPL-3), que consulta
``ir.config_parameter`` antes de permitir el signup:

    get_param('auth_signup.invitation_scope', 'b2b')  # 'b2c' => free signup
    get_param('auth_signup.reset_password')           # reset habilitado

Aquí la política vive en ``SystemParameter`` (L2) — editable en caliente. NADA
cableado en las vistas: consultan estos helpers, que leen L2 y caen a "abierto"
(default 'b2c' de un e-commerce) sólo si la clave no fue sembrada.
"""
from addons.base.models import SystemParameter

# Claves L2 (equivalentes a los config-params de Odoo auth_signup).
PARAM_ALLOW_UNINVITED = 'authz.signup_allow_uninvited'
PARAM_RESET_PASSWORD = 'authz.signup_reset_password'

# Fallback si la clave no existe: registro/reset ABIERTOS (Odoo 'b2c' — el
# caso natural de un e-commerce). El valor real se siembra en L2 (migración
# 0001) y es editable; este fallback no es un flag cableado de comportamiento,
# es el neutro "sin política => e-commerce abierto".
_ABSENT_OPEN = '1'

_TRUE = {'1', 'true', 'True', 'b2c', 'yes'}


def _flag(key):
    return str(SystemParameter.get_param(key, _ABSENT_OPEN)) in _TRUE


def signup_open():
    """True si el auto-registro público está permitido (Odoo 'b2c')."""
    return _flag(PARAM_ALLOW_UNINVITED)


def password_reset_enabled():
    """True si el reset de contraseña desde login está permitido."""
    return _flag(PARAM_RESET_PASSWORD)
