"""Vistas de sesion de servidor (ADR-018, DEC-STF-AUTH-COOKIE).

Tras la migracion completa (analisis-incidente-csrf-mutaciones, Opcion 3),
la sesion de servidor es la **unica** auth del SPA. Estas vistas permiten:

  - al arrancar (o tras recargar), consultar el estado de sesion. El navegador
    manda la cookie ``sessionid`` sola, asi que la sesion se **restaura** sin
    depender de ningun token en memoria (que la recarga perderia);
  - cerrar la sesion de servidor.

No hay token CSRF: la defensa CSRF es ``SameSite=Strict`` + prefijo ``__Host-``
de la cookie de sesion (ver ``CsrfExemptSessionAuthentication`` y base.py).
"""
from django.contrib.auth import logout as django_logout
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.contrib.sessions.models import Session
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserSession


def _device_label(user_agent):
    """Etiqueta corta del dispositivo/navegador a partir del user-agent."""
    ua = (user_agent or '').lower()
    if not ua:
        return 'Dispositivo desconocido'
    if 'edg' in ua:
        browser = 'Edge'
    elif 'chrome' in ua:
        browser = 'Chrome'
    elif 'firefox' in ua:
        browser = 'Firefox'
    elif 'safari' in ua:
        browser = 'Safari'
    else:
        browser = 'Navegador'
    if 'windows' in ua:
        os_name = 'Windows'
    elif 'mac os' in ua or 'macintosh' in ua:
        os_name = 'macOS'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'iphone' in ua or 'ipad' in ua or 'ios' in ua:
        os_name = 'iOS'
    elif 'linux' in ua:
        os_name = 'Linux'
    else:
        os_name = ''
    return f'{browser} · {os_name}' if os_name else browser


def _user_payload(user):
    """Mismo shape que el objeto ``user`` del login (FR-AUTH-02.15)."""
    return {
        'id':         user.pk,
        'username':   user.email,
        'email':      user.email,
        'first_name': user.first_name,
        'last_name':  user.last_name,
        'is_staff':   user.is_staff,
        'avatar_url': user.get_avatar_url(),
    }


class SessionStatusView(APIView):
    """``GET`` — estado de la sesion de servidor.

    Accesible sin autenticacion: devuelve ``isAuthenticated=false`` para
    anonimos. Ya no siembra ni entrega token CSRF (la defensa CSRF es
    ``SameSite=Strict``); el SPA solo necesita saber si hay sesion + el user.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Estado de sesion de servidor',
        description=(
            'Devuelve si hay sesion activa (cookie HttpOnly) y el objeto user. '
            'Auth unica del SPA tras la migracion a sesion (ADR-018).'
        ),
        responses={200: OpenApiResponse(description='Estado de sesion.')},
        tags=['auth'],
    )
    def get(self, request):
        user = request.user
        authenticated = bool(user and user.is_authenticated)
        return Response({
            'isAuthenticated': authenticated,
            'user': _user_payload(user) if authenticated else None,
        })


class SessionLogoutView(APIView):
    """``POST`` — cierra la sesion de servidor (borra la fila de sesion)."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Cerrar sesion de servidor',
        description='Llama a django.contrib.auth.logout: borra la sesion actual.',
        responses={204: OpenApiResponse(description='Sesion cerrada.')},
        tags=['auth'],
    )
    def post(self, request):
        django_logout(request)
        return Response(status=204)


class SessionListView(APIView):
    """``GET`` — sesiones activas del usuario (UC-AUTH-17 / H-16).

    Devuelve solo las sesiones cuyo ``session_key`` sigue vivo en
    ``django_session`` (no expiradas ni cerradas). No expone el ``session_key``
    ni datos de otros usuarios (RNF-SEC-003). La IP es dato personal: solo el
    propio dueño la ve (BR-013).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Sesiones activas del usuario',
        responses={200: OpenApiResponse(description='Lista de sesiones activas.')},
        tags=['auth'],
    )
    def get(self, request):
        rows = list(UserSession.objects.filter(user=request.user))
        keys = [r.session_key for r in rows]
        valid = set(
            Session.objects.filter(session_key__in=keys)
            .values_list('session_key', flat=True)
        )
        current = request.session.session_key
        data = [
            {
                'id':            r.pk,
                'ip_address':    r.ip_address,
                'device':        _device_label(r.user_agent),
                'created_at':    r.created_at.isoformat(),
                'last_activity': r.last_activity.isoformat(),
                'is_current':    r.session_key == current,
            }
            for r in rows if r.session_key in valid
        ]
        return Response({'results': data, 'count': len(data)})


class SessionRevokeView(APIView):
    """``POST`` — cerrar una sesión específica del usuario (UC-AUTH-17).

    Borra la fila de ``django_session`` (invalida la cookie) y el registro
    ``UserSession``. Aislado por usuario: una sesión ajena responde 404 sin
    revelar existencia (RNF-SEC-003).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Cerrar una sesión específica',
        responses={204: OpenApiResponse(description='Sesión cerrada.')},
        tags=['auth'],
    )
    def post(self, request, pk):
        try:
            us = UserSession.objects.get(pk=pk, user=request.user)
        except UserSession.DoesNotExist:
            return Response(
                {'detail': 'Sesión no encontrada.',
                 'codigo_error': 'SESSION_NOT_FOUND'},
                status=404,
            )
        Session.objects.filter(session_key=us.session_key).delete()
        us.delete()
        return Response(status=204)
