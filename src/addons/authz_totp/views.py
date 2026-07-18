"""Vistas — addons.authz_totp (gestión del 2FA del usuario autenticado).

Endpoints ``/api/v2/authz/totp/`` (nunca ``{user_id}`` — el 2FA es del propio
usuario). El gate del segundo factor en el **login** vive en
``users.tokens.PYTokenObtainPairSerializer`` (consulta ``totp_enabled`` /
``verify_code`` de este módulo).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz_totp.serializers import TotpCodeSerializer
from addons.authz_totp.services import (
    begin_setup,
    confirm_setup,
    disable,
    totp_enabled,
)


class TotpStatusView(APIView):
    """GET — ¿el usuario tiene 2FA TOTP activo?"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'enabled': totp_enabled(request.user)})


class TotpSetupView(APIView):
    """POST — inicia el alta: devuelve el secreto + URI de aprovisionamiento
    (para el QR). Aún NO activa el 2FA (hay que confirmar un código)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = begin_setup(request.user)
        if result is None:
            return Response(
                {'codigo_error': 'TOTP_ALREADY_ENABLED',
                 'detail': 'El 2FA ya está activo. Desactívalo antes de reconfigurar.'},
                status=409,
            )
        secret, uri = result
        return Response({'secret': secret, 'otpauth_uri': uri}, status=201)


class TotpConfirmView(APIView):
    """POST {code} — verifica el primer código y ACTIVA el 2FA."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TotpCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        if not confirm_setup(request.user, serializer.validated_data['code']):
            return Response(
                {'codigo_error': 'TOTP_INVALID',
                 'detail': 'Código inválido o no hay un alta pendiente.'},
                status=400,
            )
        return Response({'enabled': True}, status=200)


class TotpDisableView(APIView):
    """POST {code} — desactiva el 2FA confirmando un código actual."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TotpCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        if not disable(request.user, serializer.validated_data['code']):
            return Response(
                {'codigo_error': 'TOTP_INVALID',
                 'detail': 'Código inválido o el 2FA no está activo.'},
                status=400,
            )
        return Response({'enabled': False}, status=200)
