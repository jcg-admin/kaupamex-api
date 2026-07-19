"""``NewsletterConfirmView`` — confirmación del doble opt-in (UC-NEW-01).

POST /api/v2/newsletter/subscriptions/confirmations/. ``NewsletterConfirmV2View``
toma el token del body; la vista base lo recibe por parámetro.
"""
from django.core import signing
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from addons.mass_mailing import services as mm
from config.schema import error_response


class NewsletterConfirmView(APIView):
    """POST /api/v2/newsletter/.../confirmations/ — UC-NEW-01 double opt-in."""
    permission_classes = [AllowAny]
    # H-CICLO26-02: throttle para limitar intentos de fuerza bruta sobre tokens.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'newsletter_confirm'

    @extend_schema(
        summary='Confirmar suscripción al newsletter (UC-NEW-01)',
        tags=['newsletter'],
        request=None,
        responses={200: None,
                   400: error_response('Token expirado'),
                   404: error_response('Token inválido')},
    )
    def post(self, request, token):
        try:
            email = signing.loads(
                token, salt='newsletter-confirm', max_age=86400,  # 24h
            )
        except signing.SignatureExpired:
            return Response(
                {'detail': 'Token expirado.', 'codigo_error': 'TOKEN_EXPIRED'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            raise NotFound({'detail': 'Token inválido.', 'codigo_error': 'INVALID_TOKEN'})

        sub = mm.find_by_confirmation_token(email, token)
        if not sub:
            raise NotFound({'detail': 'Token no encontrado.', 'codigo_error': 'INVALID_TOKEN'})

        mm.confirm(sub)
        return Response(mm.serialize_item(sub))


class NewsletterConfirmV2View(APIView):
    """POST /api/v2/newsletter/subscriptions/confirmations/ — Tier B.

    v1 had token in URL path; v2 takes token from request body.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        if not token:
            return Response(
                {'detail': 'token requerido.', 'codigo_error': 'TOKEN_REQUIRED'},
                status=400,
            )
        try:
            return NewsletterConfirmView().post(request, token=token)
        except NotFound:
            return Response(
                {'detail': 'Token inválido.', 'codigo_error': 'INVALID_TOKEN'},
                status=400,
            )
