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

from django.apps import apps as django_apps
from django.contrib.auth import authenticate, login
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from exceptions import UserError

from addons.authz_password_policy.validators import get_password_policy
from addons.authz_signup.models import res_partner as partner_svc
from addons.authz_signup.models import res_users as signup_svc
from addons.authz_signup.models.policy import (
    password_reset_enabled,
    signup_open,
)
from addons.authz_signup.controllers.serializers import (
    RequestResetSerializer,
    SignupSerializer,
    VerifyEmailSerializer,
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
        200: OpenApiResponse(
            description='name/login/email del token + '
                        'password_minimum_length'),
        400: OpenApiResponse(description='SIGNUP_INVALID_TOKEN'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def signup_info(request):
    """≙ ``_signup_retrieve_info`` expuesto — pre-auth.

    ``password_minimum_length`` viaja en el payload — fold del puente
    ``auth_password_policy_signup`` de la referencia, cuyo único dominio
    es añadir esa clave a ``get_auth_signup_config`` para que la pantalla
    de set-password pinte la política antes de enviar.
    """
    token = request.query_params.get('token', '')
    info = partner_svc.signup_retrieve_info(token) if token else None
    if info is None:
        return Response(
            {'codigo_error': 'SIGNUP_INVALID_TOKEN',
             'detail': 'Signup token is not valid or expired.'},
            status=status.HTTP_400_BAD_REQUEST)
    info['password_minimum_length'] = get_password_policy()['minlength']
    return Response(info)


@extend_schema(
    tags=['authz-signup'],
    summary='Verificar el correo con el token, o reenviar el enlace',
    request=VerifyEmailSerializer,
    responses={
        200: OpenApiResponse(
            description='Con token: cuenta activada y sesión abierta. '
                        'Con login: si la cuenta existe, se reenvió el correo'),
        400: OpenApiResponse(description='VERIFY_INVALID_TOKEN | '
                                         'VERIFY_PAYLOAD_REQUIRED'),
    },
    auth=[],
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """Verificación de correo — pre-auth. **Forma propia**, no un puerto.

    La referencia no tiene este flujo: allí el alta llega por invitación al
    buzón, así que el signup mismo prueba el correo. Ver
    ``SignupRequest.TYPE_VERIFY`` para la medición sobre ``odoo19c:``.

    Dos operaciones sobre la misma ruta, según el payload:

    - ``{token}`` → consume el enlace, activa la cuenta y **abre sesión**.
      El auto-login es decisión vigente (``analisis-auto-login-verificacion-
      email``): hacer clic en el enlace prueba control del buzón, el mismo
      nivel de confianza que el reset — y sin él el usuario cae en una
      pantalla sin salida.
    - ``{login}`` → reenvía el correo. Responde 200 **siempre**, exista o no
      la cuenta: revelar lo contrario es enumeración de usuarios (mismo
      criterio que ``request_reset``).
    """
    serializer = VerifyEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    token = serializer.validated_data['token']
    loginname = serializer.validated_data['login']

    if token:
        try:
            user = signup_svc.verify_email(token)
        except UserError as exc:
            return Response(
                {'codigo_error': 'VERIFY_INVALID_TOKEN', 'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        # Sin ``authenticate`` no hay backend en el usuario; se nombra el
        # backend de credenciales explícitamente porque el proyecto tiene
        # cuatro registrados y Django sólo lo infiere cuando hay uno.
        login(request, user,
              backend='django.contrib.auth.backends.ModelBackend')
        return Response({'login': user.login, 'isAuthenticated': True})

    if not loginname:
        return Response(
            {'codigo_error': 'VERIFY_PAYLOAD_REQUIRED',
             'detail': 'Provide either a token or a login.'},
            status=status.HTTP_400_BAD_REQUEST)

    ResUsers = django_apps.get_model('base', 'ResUsers')
    user = ResUsers.objects.filter(login__iexact=loginname).first()
    if user is not None:
        try:
            signup_svc.send_verification_email(user)
        except UserError as exc:
            _logger.info('Verification resend skipped for <%s>: %s',
                         loginname, exc)
    else:
        _logger.info('Verification resend for unknown login <%s>', loginname)
    return Response(status=status.HTTP_200_OK)
