"""Sesión del cliente — adaptación de ``odoo19c: addons/web/controllers/session.py``.

Las cuatro rutas de sesión de la referencia, adaptadas al contrato REST del
producto. El mecanismo NO se reimplementa: Django ya provee sesión de servidor,
que es justo lo que ADR-018 declara como autenticación por defecto.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===============================  ============================================
Referencia                       Aquí
===============================  ============================================
``/web/session/authenticate``    ``POST /api/v2/web/session/authenticate/``
``:31``, ``jsonrpc``,            ``AllowAny`` — el login es pre-auth
``auth="none"``
-------------------------------  --------------------------------------------
``/web/session/destroy``         ``POST /api/v2/web/session/destroy/``
``:84``, ``jsonrpc``,            ``IsAuthenticated``
``auth='user'``
-------------------------------  --------------------------------------------
``/web/session/logout``          ``POST /api/v2/web/session/logout/``
``:88``, ``http``, ``auth='none'``  ``AllowAny`` — idempotente
-------------------------------  --------------------------------------------
``/web/session/get_session_info``  ``GET /api/v2/web/session/``
``:25``, ``auth='user'``
===============================  ============================================

Tres divergencias declaradas
=============================

1. **Sin parámetro ``db``.** La referencia lo recibe y valida contra
   ``http.db_filter`` porque un servidor sirve N bases. Aquí la base es una y
   la fija el despliegue; aceptarlo sería superficie sin función.
2. **``logout`` no redirige.** La referencia devuelve un 303 a ``/odoo``
   porque su cliente es una página. El nuestro es un cliente REST: 204.
3. **``destroy`` y ``logout`` hacen lo mismo.** En la referencia difieren en
   el tipo de transporte (``jsonrpc`` vs ``http``) y en si conservan la base
   (``keep_db``); ninguna de las dos distinciones sobrevive aquí. Se conservan
   ambas rutas porque son contrato publicado de la referencia, no por aportar
   comportamientos distintos.

Lo que esta adaptación NO cubre
================================

El segundo factor. La referencia difiere la finalización de la sesión cuando
``user._mfa_url()`` devuelve algo (``odoo19c: odoo/http.py:1256-1258``): fija
``pre_uid`` y espera al segundo factor. Aquí ``authz_totp`` existe pero sólo
expone gestión (alta, confirmación, baja), no un corte en el login. Cerrar esa
brecha es trabajo propio y se declara, no se simula.
"""
from django.contrib.auth import authenticate, login, logout
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from addons.authz.services import is_superadmin
from addons.web.controllers.serializers import CredentialSerializer, SessionInfoSerializer


def _session_info(user):
    """≙ ``ir.http.session_info()`` de la referencia, recortado a lo publicado.

    La referencia devuelve además la versión del servidor, los módulos
    instalados y la configuración del cliente web. Nada de eso tiene consumidor
    en un cliente REST, así que no se emite.
    """
    # ``partner`` es obligatorio en el modelo (la referencia no admite usuario
    # sin partner), así que no se guarda contra su ausencia.
    #
    # ``is_system`` sale de ``is_superadmin``, no de un flag del modelo: aquí
    # el acceso administrativo es una CAPACIDAD (DEC-11) y ``ResUsers`` no
    # declara ``is_superuser``/``is_staff``. En la referencia el equivalente es
    # ``user._is_system()`` (pertenencia a ``base.group_system``) —también una
    # pertenencia, no una columna—, así que la correspondencia es directa.
    return {
        'uid': user.pk,
        'login': user.login,
        'name': user.partner.name,
        'is_system': is_superadmin(user),
    }


@extend_schema(
    tags=['web'],
    summary='Abrir sesión con credencial',
    request=CredentialSerializer,
    responses={
        200: SessionInfoSerializer,
        400: OpenApiResponse(description='CREDENTIAL_REQUIRED'),
        401: OpenApiResponse(description='INVALID_CREDENTIAL'),
    },
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def session_authenticate(request):
    """≙ ``/web/session/authenticate`` — pre-auth.

    ``login()`` de Django cicla la clave de sesión, que es lo que la referencia
    pide con ``should_rotate`` (``odoo19c: odoo/http.py:1293``): una sesión
    abierta nunca reusa el identificador de la anónima previa.
    """
    serializer = CredentialSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'codigo_error': 'CREDENTIAL_REQUIRED',
             'detail': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(
        request,
        username=serializer.validated_data['login'],
        password=serializer.validated_data['password'],
    )
    if user is None:
        # Un solo código para credencial errónea y cuenta inexistente: separar
        # los dos casos revelaría qué logins existen.
        return Response(
            {'codigo_error': 'INVALID_CREDENTIAL',
             'detail': 'Credencial inválida.'},
            status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    return Response(_session_info(user))


@extend_schema(
    tags=['web'],
    summary='Ver la sesión activa',
    responses={200: SessionInfoSerializer},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_info(request):
    """≙ ``/web/session/get_session_info``."""
    return Response(_session_info(request.user))


@extend_schema(
    tags=['web'],
    summary='Cerrar la sesión activa',
    request=None,
    responses={204: OpenApiResponse(description='Sesión cerrada')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def session_destroy(request):
    """≙ ``/web/session/destroy`` — exige sesión, como la referencia."""
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['web'],
    summary='Cerrar sesión (idempotente)',
    request=None,
    responses={204: OpenApiResponse(description='Sin sesión activa')},
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def session_logout(request):
    """≙ ``/web/session/logout`` — ``auth='none'`` en la referencia.

    Sin sesión activa devuelve 204 igual: cerrar lo que ya está cerrado no es
    un error, y exigir sesión daría un 401 que le dice al cliente que su
    sesión caducó justo cuando quiere deshacerse de ella.
    """
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)
