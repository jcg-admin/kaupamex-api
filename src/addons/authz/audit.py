"""Auditoría de eventos de autorización (DEC-07) — addons.authz.

Un concern por módulo (SOL-094 frente B): registro append-only de ``AuthzEvent``
PII-safe. No bloqueante — un fallo del audit jamás rompe la request original
(DEC-LOG-04). Antes vivía mezclado en ``services.py``.
"""
from addons.authz.models import AuthzEvent


def _client_ip(request):
    xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return xff or request.META.get('REMOTE_ADDR') or None


def _session_key(request):
    return getattr(getattr(request, 'session', None), 'session_key', '') or ''


def audit_authz_event(request, action, code, extra=None):
    """Registra un ``AuthzEvent`` (DEC-07) PII-safe. No bloqueante: un fallo del
    audit jamás rompe la request original (mismo criterio DEC-LOG-04)."""
    try:
        actor = getattr(request, 'user', None)
        if not getattr(actor, 'is_authenticated', False):
            actor = None
        AuthzEvent.objects.create(
            actor=actor,
            action=action,
            capability_code=code or '',
            ip_addr=_client_ip(request),
            correlation_id=getattr(request, 'correlation_id', '') or '',
            extra_json=extra,
        )
    except Exception:
        # silent OK because DEC-LOG-04: sellar la auditoría nunca debe romper el
        # flujo de autorización ni la respuesta al cliente.
        pass
