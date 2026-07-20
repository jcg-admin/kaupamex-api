"""Vistas — addons.auth_totp (gestión del 2FA del usuario autenticado).

Endpoints ``/api/v2/authz/totp/`` (nunca ``{user_id}`` — el 2FA es del propio
usuario). **Function-based views** (``@api_view`` + ``@require_capability``):
son acciones de un solo verbo (setup/confirm/disable/status/regenerar), donde el
boilerplate de una clase por método no aporta (convención de vistas de acción
única, ver ``CLAUDE.md`` de api). Se gobiernan por la capacidad de cuenta propia
``account.security`` (DEC-ENF-01: sembrada en TODOS los roles vía ``seed_authz``)
— NO ``IsAuthenticated`` a secas (que saltaría el modelo de capacidades). El gate
del segundo factor en el **login** vive en
``users.tokens.PYTokenObtainPairSerializer`` (``totp_enabled`` / ``verify_code`` /
``consume_recovery_code``).
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.auth_totp.serializers import TotpCodeSerializer, TotpDisableSerializer
from addons.auth_totp.services import (
    begin_setup,
    confirm_setup,
    count_recovery_codes,
    disable,
    generate_recovery_codes,
    totp_enabled,
    verify_code,
)

_TAGS = ['authz-2fa']
_CAP = 'account.security'


@extend_schema(
    tags=_TAGS,
    summary='Estado del 2FA del usuario',
    responses={200: OpenApiResponse(
        description='{enabled: bool, recovery_codes_remaining: int}')},
)
@api_view(['GET'])
@require_capability(_CAP)
def totp_status(request):
    """GET — ¿el usuario tiene 2FA TOTP activo? + códigos de recuperación
    restantes."""
    return Response({
        'enabled': totp_enabled(request.user),
        'recovery_codes_remaining': count_recovery_codes(request.user),
    })


@extend_schema(
    tags=_TAGS,
    summary='Iniciar alta de 2FA (secreto + otpauth URI)',
    request=None,
    responses={
        201: OpenApiResponse(description='{secret, otpauth_uri}'),
        409: OpenApiResponse(description='TOTP_ALREADY_ENABLED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_setup(request):
    """POST — inicia el alta: devuelve el secreto + URI de aprovisionamiento
    (para el QR). Aún NO activa el 2FA (hay que confirmar un código)."""
    result = begin_setup(request.user)
    if result is None:
        return Response(
            {'codigo_error': 'TOTP_ALREADY_ENABLED',
             'detail': 'El 2FA ya está activo. Desactívalo antes de reconfigurar.'},
            status=409,
        )
    secret, uri = result
    return Response({'secret': secret, 'otpauth_uri': uri}, status=201)


@extend_schema(
    tags=_TAGS,
    summary='Confirmar y activar el 2FA',
    request=TotpCodeSerializer,
    responses={
        200: OpenApiResponse(description='{enabled: true, recovery_codes: [...]}'),
        400: OpenApiResponse(description='TOTP_INVALID / código malformado'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_confirm(request):
    """POST {code} — verifica el primer código y ACTIVA el 2FA."""
    serializer = TotpCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    recovery_codes = confirm_setup(request.user, serializer.validated_data['code'])
    if recovery_codes is None:
        return Response(
            {'codigo_error': 'TOTP_INVALID',
             'detail': 'Código inválido o no hay un alta pendiente.'},
            status=400,
        )
    # Los códigos de recuperación se muestran UNA sola vez (como Odoo).
    return Response({'enabled': True, 'recovery_codes': recovery_codes}, status=200)


@extend_schema(
    tags=_TAGS,
    summary='Desactivar el 2FA',
    request=TotpDisableSerializer,
    responses={
        200: OpenApiResponse(description='{enabled: false}'),
        400: OpenApiResponse(description='TOTP_INVALID / código malformado'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_disable(request):
    """POST {code} — desactiva el 2FA con un código TOTP actual **o** un código
    de recuperación (para quien perdió el authenticator)."""
    serializer = TotpDisableSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    if not disable(request.user, serializer.validated_data['code']):
        return Response(
            {'codigo_error': 'TOTP_INVALID',
             'detail': 'Código inválido o el 2FA no está activo.'},
            status=400,
        )
    return Response({'enabled': False}, status=200)


@extend_schema(
    tags=_TAGS,
    summary='Regenerar códigos de recuperación',
    request=TotpCodeSerializer,
    responses={
        200: OpenApiResponse(description='{recovery_codes: [...]}'),
        400: OpenApiResponse(description='TOTP_INVALID / código malformado'),
        409: OpenApiResponse(description='TOTP_NOT_ENABLED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def totp_recovery_codes(request):
    """POST {code} — regenera los códigos de recuperación (invalida los
    anteriores). Requiere un código TOTP actual; sólo con 2FA activo."""
    if not totp_enabled(request.user):
        return Response(
            {'codigo_error': 'TOTP_NOT_ENABLED',
             'detail': 'El 2FA no está activo.'},
            status=409,
        )
    serializer = TotpCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    if not verify_code(request.user, serializer.validated_data['code']):
        return Response(
            {'codigo_error': 'TOTP_INVALID',
             'detail': 'Código de verificación inválido.'},
            status=400,
        )
    codes = generate_recovery_codes(request.user)
    return Response({'recovery_codes': codes}, status=200)
