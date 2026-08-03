"""Views — addons.authz_totp_mail.

Tres superficies (FBV — cada una es una acción, patrón ``authz_totp``):

- ``send-code`` / ``verify-code`` — el 2FA por correo del propio usuario
  (``account.security``, sembrada en todos los roles DEC-ENF-01). En la
  referencia el envío ocurre en la fase pre-auth del login web
  (``controllers/home.py``); ese enganche llegará con el endpoint de login
  (H-API-218) — mientras, la pareja send/verify cubre el flujo del usuario
  autenticado (mismo alcance que los endpoints de ``authz_totp``).
- ``invite`` — la acción de administrador ``action_totp_invite``
  (``permissions.totp_invite``).
"""
from django.apps import apps as django_apps
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from exceptions import AccessDenied, UserError

from addons.authz.permissions import require_capability
from addons.authz_totp_mail.models.res_users import (
    invite_users,
    send_totp_mail_code,
    verify_totp_mail_code,
)

_CAP = 'account.security'


class VerifyCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=10)


class InviteSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False)


@extend_schema(
    tags=['authz-totp-mail'],
    summary='Enviar el código 2FA por correo al usuario autenticado',
    request=None,
    responses={202: OpenApiResponse(description='Código enviado'),
               400: OpenApiResponse(description='TOTP_MAIL_SEND_FAILED')},
)
@api_view(['POST'])
@require_capability(_CAP)
def send_code(request):
    try:
        send_totp_mail_code(request.user)
    except UserError as exc:
        return Response(
            {'codigo_error': 'TOTP_MAIL_SEND_FAILED', 'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST)
    return Response(status=status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=['authz-totp-mail'],
    summary='Verificar el código 2FA recibido por correo',
    request=VerifyCodeSerializer,
    responses={200: OpenApiResponse(description='Código correcto'),
               403: OpenApiResponse(description='TOTP_MAIL_CODE_INVALID')},
)
@api_view(['POST'])
@require_capability(_CAP)
def verify_code(request):
    serializer = VerifyCodeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        verify_totp_mail_code(request.user, serializer.validated_data['code'])
    except AccessDenied as exc:
        return Response(
            {'codigo_error': 'TOTP_MAIL_CODE_INVALID', 'detail': str(exc)},
            status=status.HTTP_403_FORBIDDEN)
    return Response({'verified': True})


@extend_schema(
    tags=['authz-totp-mail'],
    summary='Invitar usuarios a activar 2FA (correo de invitación)',
    request=InviteSerializer,
    responses={200: OpenApiResponse(
        description='Nombres de los usuarios invitados (los que ya tienen '
                    '2FA activo se omiten, igual que la referencia)')},
)
@api_view(['POST'])
@require_capability('permissions.totp_invite')
def invite(request):
    serializer = InviteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ResUsers = django_apps.get_model('base', 'ResUsers')
    users = list(ResUsers.objects.filter(
        pk__in=serializer.validated_data['user_ids'], active=True))
    invited = invite_users(users, inviter=request.user)
    return Response({'invited': invited})
