"""
Views — addons.referral (UC-PRO-05: programa de referidos)

GET  /api/v1/account/referral/         — codigo + stats del usuario autenticado
POST /api/v1/account/referral/redeem/  — canjear un codigo referral
"""
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability

from addons.base.models import SiteSettings
from addons.loyalty.models import ReferralCode, Referral
from .serializers import ReferralStatusSerializer, RedeemReferralSerializer
from .services import redeem_referral_code, ReferralError


def _program_active() -> bool:
    return bool(SiteSettings.get_current().referral_active)


def _not_found_response():
    return Response(
        {'detail': 'Recurso no encontrado.', 'codigo_error': 'NOT_FOUND'},
        status=404,
    )


class ReferralView(APIView):
    """GET — codigo referral + estadisticas del comprador autenticado."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.referral'

    @extend_schema(
        summary='Codigo referral del comprador (UC-PRO-05 Subflujo A)',
        description=(
            'Devuelve el codigo referral del usuario autenticado, generandolo '
            'si no existe, junto con el enlace para compartir y las '
            'estadisticas de referidos. Retorna 404 si el programa de '
            'referidos esta desactivado (EX-01).'
        ),
        responses={
            200: ReferralStatusSerializer,
            404: OpenApiResponse(description='Programa de referidos desactivado (codigo_error=NOT_FOUND).'),
        },
        tags=['referral'],
    )
    def get(self, request):
        if not _program_active():
            return _not_found_response()
        referral_code = ReferralCode.get_or_create_for_user(request.user)
        referrals = Referral.objects.filter(referrer=request.user)
        completed = referrals.filter(status=Referral.STATUS_COMPLETED)
        frontend = getattr(settings, 'FRONTEND_URL', '')
        share_link = f'{frontend}/register?ref={referral_code.code}'
        data = {
            'code': referral_code.code,
            'share_link': share_link,
            'total_referrals': referrals.count(),
            'completed_referrals': completed.count(),
            'rewards_earned': completed.exclude(reward_voucher__isnull=True).count(),
        }
        return Response(ReferralStatusSerializer(data).data)


class RedeemReferralView(APIView):
    """POST — el referido canjea un codigo referral (UC-PRO-05 Subflujo B)."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.referral'

    @extend_schema(
        summary='[DEPRECATED → /api/v2/account/referral/redemptions/] Canjear codigo referral (UC-PRO-05 Subflujo B)',
        deprecated=True,
        request=RedeemReferralSerializer,
        responses={
            201: OpenApiResponse(description='Relacion de referido creada en estado PENDING.'),
            400: OpenApiResponse(description='Payload invalido (codigo_error=INVALID_PAYLOAD).'),
            404: OpenApiResponse(description='Codigo inexistente o programa desactivado (codigo_error=NOT_FOUND).'),
            409: OpenApiResponse(description='El usuario ya canjeo un codigo (codigo_error=CONFLICT).'),
            422: OpenApiResponse(description='Autorreferencia o codigo inactivo (codigo_error SELF_REFERRAL_NOT_ALLOWED|VOUCHER_INACTIVE).'),
        },
        tags=['referral'],
    )
    def post(self, request):
        if not _program_active():
            return _not_found_response()
        serializer = RedeemReferralSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'detail': serializer.errors, 'codigo_error': 'INVALID_PAYLOAD'},
                status=400,
            )
        try:
            referral = redeem_referral_code(request.user, serializer.validated_data['code'])
        except ReferralError as exc:
            return Response(
                {'detail': exc.detail, 'codigo_error': exc.codigo_error},
                status=exc.http_status,
            )
        return Response(
            {'status': 'OK', 'referral_id': referral.id, 'referral_status': referral.status},
            status=201,
        )
