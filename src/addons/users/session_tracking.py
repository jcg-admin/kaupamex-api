"""
Registro de sesiones activas (UC-AUTH-17 / H-16).

``record_user_session`` se llama justo después de ``django_login`` en cada punto
de login para guardar IP + user-agent contra el ``session_key`` de la sesión
recién creada. Módulo aparte (imports al top-level) para no meter lógica ni
imports diferidos en las vistas de login.
"""
from .models import UserSession


def client_ip(request):
    """IP del cliente: primer valor de X-Forwarded-For, si no REMOTE_ADDR."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def record_user_session(request, user):
    """Registra/actualiza la sesión activa del usuario tras el login.

    El ``session_key`` existe tras ``django_login``; si aún no, se fuerza el
    guardado de la sesión. Silencioso ante cualquier fallo: registrar la sesión
    NUNCA debe romper el login.
    """
    try:
        session = getattr(request, 'session', None)
        if session is None:
            return
        key = session.session_key
        if not key:
            session.save()
            key = session.session_key
        if not key:
            return
        UserSession.objects.update_or_create(
            session_key=key,
            defaults={
                'user':       user,
                'ip_address': client_ip(request),
                'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:400],
            },
        )
    except Exception:  # noqa: BLE001
        # silent OK because session tracking is telemetry: a failure here
        # must never break the login flow.
        pass
