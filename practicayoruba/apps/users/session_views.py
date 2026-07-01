"""Vistas de sesion de servidor (ADR-018, DEC-STF-AUTH-COOKIE).

Aditivas sobre el login JWT. Permiten que el SPA:
  - al arrancar (o tras recargar), consulte el estado de sesion. Como el
    navegador manda la cookie ``sessionid`` sola, la sesion se **restaura** sin
    depender del token JWT en memoria (que la recarga pierde);
  - obtenga el token CSRF (Opcion B, ``CSRF_USE_SESSIONS``) para las mutaciones
    autenticadas por sesion;
  - cierre la sesion de servidor.

No retiran el flujo JWT existente.
"""
from django.contrib.auth import logout as django_logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


def _user_payload(user):
    """Mismo shape que el objeto ``user`` del login JWT (FR-AUTH-02.15)."""
    return {
        'id':         user.pk,
        'username':   user.username,
        'email':      user.email,
        'first_name': user.first_name,
        'last_name':  user.last_name,
        'is_staff':   user.is_staff,
        'avatar_url': user.get_avatar_url(),
    }


class SessionStatusView(APIView):
    """``GET`` — estado de la sesion + siembra del token CSRF.

    Accesible sin autenticacion: devuelve ``isAuthenticated=false`` para
    anonimos. ``@ensure_csrf_cookie`` fuerza que el secreto CSRF quede en la
    sesion; ``get_token`` entrega el token enmascarado en el cuerpo para que el
    SPA lo mande en ``X-CSRFToken``.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Estado de sesion de servidor + token CSRF',
        description=(
            'Devuelve si hay sesion activa (cookie HttpOnly) y el objeto user. '
            'Incluye csrfToken para mutaciones autenticadas por sesion (ADR-018).'
        ),
        responses={200: OpenApiResponse(description='Estado de sesion.')},
        tags=['auth'],
    )
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        user = request.user
        authenticated = bool(user and user.is_authenticated)
        return Response({
            'isAuthenticated': authenticated,
            'user': _user_payload(user) if authenticated else None,
            'csrfToken': get_token(request),
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
