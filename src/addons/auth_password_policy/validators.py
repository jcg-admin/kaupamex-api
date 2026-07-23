"""Política de contraseña configurable en caliente — addons.auth_password_policy.

Adaptado de ``auth_password_policy/models/res_users.py`` de Odoo (LGPL-3):

    def get_password_policy(self):
        return {'minlength': int(params.get_param('auth_password_policy.minlength', 0))}
    def _check_password_policy(self, passwords): ...  # len(pwd) < minlength -> error

La diferencia con Django puro: ``MinimumLengthValidator`` cablea ``min_length``
en ``settings`` (estático). Odoo lo hace **editable en runtime** vía
``ir.config_parameter``. Este validador replica eso leyendo
``authz.password_minlength`` de ``SystemParameter`` (L2) en cada validación —
el admin cambia la política sin redeploy, igual que en Odoo.

Se conecta con la API nativa ``AUTH_PASSWORD_VALIDATORS``, así corre en todos
los caminos que ya llaman ``django.contrib.auth.password_validation.
validate_password`` (registro y cambio de contraseña en ``users.serializers``).
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from addons.base.models import SystemParameter

# Clave de config L2 (equivalente a ``auth_password_policy.minlength`` de Odoo).
# NADA hardcoded: el valor vive SOLO en ``SystemParameter`` (sembrado por la
# migración 0001 con '8', editable en caliente). El fallback ``0`` es el mismo
# de Odoo (``get_param('auth_password_policy.minlength', default=0)``): si la
# clave no existe -> política deshabilitada, no un mínimo cableado en el código.
PARAM_MINLENGTH = 'authz.password_minlength'
_ABSENT_POLICY = 0  # Odoo default: sin clave L2 => sin enforcement (no es un mínimo)


def get_password_policy():
    """Devuelve la política vigente (equivalente a ``get_password_policy`` de
    Odoo). Lee de ``SystemParameter`` L2, editable en caliente; el valor nunca
    está cableado en el código."""
    return {
        'minlength': int(SystemParameter.get_param(PARAM_MINLENGTH, _ABSENT_POLICY)),
    }


class ConfigurablePasswordPolicyValidator:
    """Longitud mínima de contraseña leída de ``SystemParameter`` (runtime).

    Reemplaza a ``MinimumLengthValidator`` de Django: mismo efecto (rechaza
    contraseñas cortas) pero la cota se lee de L2 en vez de ``settings``, así
    es editable en caliente por el admin — el comportamiento de Odoo
    ``auth_password_policy``.
    """

    def validate(self, password, user=None):
        minlength = get_password_policy()['minlength']
        if minlength and len(password) < minlength:
            raise ValidationError(
                _('Tu contraseña debe contener al menos %(minlength)d '
                  'caracteres y solo tiene %(length)d.'),
                code='password_too_short',
                params={'minlength': minlength, 'length': len(password)},
            )

    def get_help_text(self):
        minlength = get_password_policy()['minlength']
        return _('Tu contraseña debe contener al menos %(minlength)d caracteres.') % {
            'minlength': minlength,
        }
