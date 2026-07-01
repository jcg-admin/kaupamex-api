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
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


def _user_payload(user):
    """Mismo shape que el objeto ``user`` del login (FR-AUTH-02.15)."""
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
