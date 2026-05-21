"""
audit.py — apps.users

Helper para emitir eventos AuthEvent via
``transaction.on_commit`` (insert no bloqueante). Ver
iniciativa ``audit-log-eventos-auth`` decisiones DEC-AL-3
(PII safe), DEC-AL-4 (on_commit), DEC-AL-5 (signature).
"""
from django.db import transaction
from .models import AuthEvent


def _extract_ip(request) -> str | None:
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def audit_log_auth(user, action, request, reason: str = '', extra: dict | None = None):
    """
    Crea un AuthEvent. Usa transaction.on_commit cuando hay
    transaction activa para no bloquear, fallback directo si
    no hay transaction (e.g. AuthenticationFailed exception
    paths que abortan el atomic block).

    Argumentos:
      user:    User instance o None (login_fail sin user resuelto).
      action:  AuthEvent.ACTION_* constante.
      request: HttpRequest (o None en tareas async / signals).
      reason:  AuthEvent.REASON_* opcional.
      extra:   dict opcional. NUNCA debe contener password ni token
               en claro (DEC-AL-3).
    """
    ip_addr    = _extract_ip(request)
    user_agent = (
        request.META.get('HTTP_USER_AGENT', '')[:255]
        if request is not None else ''
    )

    def _create():
        AuthEvent.objects.create(
            user=user,
            action=action,
            ip_addr=ip_addr,
            user_agent=user_agent,
            reason=(reason or '')[:30],
            extra_json=extra,
        )

    if transaction.get_autocommit():
        # Sin atomic block: insert directo.
        _create()
    else:
        # Con atomic block: on_commit asegura que el evento
        # se cree solo si la transaccion commitea.
        transaction.on_commit(_create)
