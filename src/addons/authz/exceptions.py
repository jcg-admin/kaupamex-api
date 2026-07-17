"""Excepciones — addons.authz.

``ReauthRequired`` es la denegación **machine-readable** de DEC-12: cuando una
acción sensible se intenta sin una sesión elevada fresca, el gate en
``HasCapability`` la lanza y DRF la renderiza como ``403`` con la clave canónica
``codigo_error`` (pretix devuelve un 403 opaco / redirect; nuestra API expone el
código para que el SPA abra el modal de re-password y reintente la acción).

Diseño: :ref:`analisis-diseno-reauth-sensibles-dec12`.
"""
from rest_framework.exceptions import APIException

REAUTH_URL = '/api/v2/authz/reauth/'


class ReauthRequired(APIException):
    """403 ``REAUTH_REQUIRED`` — falta una sesión elevada fresca (DEC-12)."""

    status_code = 403
    default_code = 'reauth_required'

    def __init__(self, window_seconds):
        super().__init__(detail={
            'detail': 'Confirma tu identidad para esta acción sensible.',
            'codigo_error': 'REAUTH_REQUIRED',
            'reauth_url': REAUTH_URL,
            'window_seconds': window_seconds,
        })
