"""Re-autenticación para acciones sensibles (DEC-12) — addons.authz_reauth.

Un concern por módulo (SOL-094 frente B): sesiones reautenticadas
(``ReauthSession``) y el gate ``assert_session_fresh`` invocado desde
``HasCapability`` tras confirmar la capacidad — data-driven, sin cablear vista
por vista. El **superadmin NO está exento**: es la cuenta más privilegiada la
que DEC-12 quiere proteger. Vive en su propia app instalable (análoga a
``auth_totp`` de Odoo); ``addons.authz`` la invoca vía el facade ``services``.
"""
from datetime import timedelta

from django.utils import timezone

from addons.authz.catalog import code_requires_fresh_session
from addons.authz.exceptions import ReauthRequired
from addons.authz_audit.audit import _session_key, audit_authz_event
from addons.authz_audit.models import AuthzEvent
from addons.authz_reauth.models import ReauthSession
from addons.base.models import SystemParameter

# Código de auditoría de la re-autenticación (no es una Capability gateada; es la
# etiqueta del AuthzEvent de apertura/cierre). Deliberadamente NO "sudo".
REAUTH_CAP_CODE = 'authz.reauth'


def _reauth_ttl():
    """Segundos de vida de una sesión reautenticada (``authz.reauth_ttl`` en
    ``SystemParameter``, L2 global; default 15 min).

    Migrado desde ``settings.AUTHZ_REAUTH_TTL`` (H-API-CFG-02,
    :ref:`hallazgos-estrategia-configuracion-kaupamex`): era un tunable
    operativo global con ``default=`` cableado en código; ahora vive editable
    en caliente en L2, sembrado por la migración de datos de ``addons.base``.
    """
    return int(SystemParameter.get_param('authz.reauth_ttl', 900))


def has_active_reauth_session(user, session_key):
    """True si ``user`` tiene una sesión reautenticada vigente para
    ``session_key``."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return False
    return ReauthSession.objects.filter(
        user_id=user.pk, session_key=session_key or '',
        expires_at__gt=timezone.now(),
    ).exists()


def open_reauth_session(user, session_key, ip_addr=None):
    """Abre (o refresca) la sesión reautenticada de ``user`` para ``session_key``.

    Una fila por ``(user, session_key)``: reabrir renueva ``started_at`` y
    ``expires_at``. Devuelve la fila."""
    now = timezone.now()
    obj, _ = ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key=session_key or '',
        defaults={
            'started_at': now,
            'expires_at': now + timedelta(seconds=_reauth_ttl()),
            'ip_addr': ip_addr,
        },
    )
    return obj


def close_reauth_session(user, session_key):
    """Cierra la sesión reautenticada de ``user`` para ``session_key``."""
    ReauthSession.objects.filter(
        user_id=user.pk, session_key=session_key or '',
    ).delete()


def assert_session_fresh(request, code, unsafe_method):
    """Gate DEC-12: si ejercer ``code`` exige re-autenticación y no hay una sesión
    reautenticada fresca, audita el ``DENY`` y lanza ``ReauthRequired`` (403
    ``REAUTH_REQUIRED``).

    Invocado desde ``HasCapability.has_permission`` **después** de confirmar la
    capacidad — data-driven, sin cablear vista por vista. El **superadmin NO está
    exento**: es la cuenta más privilegiada la que DEC-12 quiere proteger."""
    if not code_requires_fresh_session(code, unsafe_method):
        return
    if has_active_reauth_session(request.user, _session_key(request)):
        return
    audit_authz_event(
        request, AuthzEvent.ACTION_DENY, code, {'reason': 'reauth_required'},
    )
    raise ReauthRequired(window_seconds=_reauth_ttl())
