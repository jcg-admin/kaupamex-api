"""Views — addons.authz_signup (alta, set-password y reset por token).

Adaptación de Odoo ``auth_signup/controllers/main.py`` (LGPL-3, leído
completo). Las tres superficies son **pre-auth** (``auth='public'`` en la
referencia): un alta o un reset no pueden exigir sesión. ``AllowAny``
explícito y documentado — la invariante "nunca ``IsAuthenticated`` a secas,
siempre capacidad" gobierna vistas de datos, no la puerta de entrada.

- ``POST signup`` → ``web_auth_signup`` (main.py): alta externa o
  set-password con token. Abre sesión al terminar.
- ``POST request-reset`` → ``web_auth_reset_password``: manda el correo con
  el enlace de set-password.
- ``GET signup-info?token=`` → ``get_auth_signup_config``/``retrieve``: datos
  del token para pintar la pantalla de set-password del SPA.
"""
import logging

from django.contrib.auth import authenticate, login
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from exceptions import UserError

from addons.authz_signup.models import res_partner as partner_svc
from addons.authz_signup.models import res_users as signup_svc
from addons.authz_signup.models.policy import (
    password_reset_enabled,
    signup_open,
)
from addons.authz_signup.controllers.serializers import (
    RequestResetSerializer,
    SignupSerializer,
)

_logger = logging.getLogger(__name__)


@extend_schema(
    tags=['authz-signup'],
    summary='Alta externa o set-password con token; abre sesión',
    request=SignupSerializer,
    responses={
        200: OpenApiResponse(description='login del usuario; sesión abierta'),
        400: OpenApiResponse(
            description='SIGNUP_INVALID_TOKEN | SIGNUP_NOT_ALLOWED | '
                        'SIGNUP_EMAIL_TAKEN'),
    },
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """≙ ``web_auth_signup`` — pre-auth.

    La política se consulta **antes** de mirar el payload, como en la
    referencia: ``auth_signup/controllers/main.py:91`` corta por
    ``reset_password_enabled`` antes de procesar nada, y ``:132`` deriva
    ``signup_enabled`` del scope de invitación. Sin este corte el gate
    existía sólo en el modelo (``authz_signup/models/res_users.py:89``) y el
    400 de validación llegaba primero, así que cerrar el alta no cerraba
    nada observable desde el endpoint.

    El token invitado es la excepción de la referencia: con token, el alta
    procede aunque el alta libre esté cerrada (es un *set-password*, no un
    registro nuevo).
    """
    if not request.data.get('token') and not signup_open():
        return Response(
            {'codigo_error': 'SIGNUP_CLOSED',
             'detail': 'El alta de cuentas está deshabilitada.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    values = {
        'login': data['login'] or None,
        'name': data['name'],
        'password': data['password'],
    }
    try:
        loginname, _password = signup_svc.signup(
            values, token=data['token'] or None)
    except signup_svc.SignupError as exc:
        return Response(
            {'codigo_error': 'SIGNUP_NOT_ALLOWED', 'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST)
    except UserError as exc:
        # token inválido/expirado o email ya registrado.
        code = ('SIGNUP_EMAIL_TAKEN' if 'already registered' in str(exc)
                else 'SIGNUP_INVALID_TOKEN')
        return Response(
            {'codigo_error': code, 'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST)

    # abrir sesión con la credencial recién fijada.
    user = authenticate(
        request, username=loginname, password=data['password'])
    if user is not None:
        login(request, user)
    return Response({'login': loginname})


@extend_schema(
    tags=['authz-signup'],
    summary='Solicitar el correo de restablecimiento de contraseña',
    request=RequestResetSerializer,
    responses={
        202: OpenApiResponse(description='Si la cuenta existe, se envió el '
                                         'correo'),
    },
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def request_reset(request):
    """≙ ``web_auth_reset_password`` — pre-auth.

    Responde 202 siempre (no revela si la cuenta existe — enumeración de
    usuarios). El envío ocurre sólo si hay cuenta.

    El corte por política va **antes** del payload, igual que
    ``auth_signup/controllers/main.py:91``.
    """
    if not password_reset_enabled():
        return Response(
            {'codigo_error': 'PASSWORD_RESET_DISABLED',
             'detail': 'El restablecimiento de contraseña está '
                       'deshabilitado.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = RequestResetSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        signup_svc.reset_password(serializer.validated_data['login'])
    except UserError as exc:
        _logger.info('Reset password requested for unknown login: %s', exc)
    return Response(status=status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=['authz-signup'],
    summary='Datos del token de signup (para la pantalla de set-password)',
    parameters=[OpenApiParameter('token', str, required=True)],
    responses={
        200: OpenApiResponse(description='name/login/email del token'),
        400: OpenApiResponse(description='SIGNUP_INVALID_TOKEN'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def signup_info(request):
    """≙ ``_signup_retrieve_info`` expuesto — pre-auth."""
    token = request.query_params.get('token', '')
    info = partner_svc.signup_retrieve_info(token) if token else None
    if info is None:
        return Response(
            {'codigo_error': 'SIGNUP_INVALID_TOKEN',
             'detail': 'Signup token is not valid or expired.'},
            status=status.HTTP_400_BAD_REQUEST)
    return Response(info)
