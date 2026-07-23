"""``NewsletterUnsubscribeView`` — baja pública por token (UC-NEW-02).

DELETE /api/v2/newsletter/subscriptions/ (vía la vista de recurso). El salt
``newsletter-unsub`` se conserva para no romper enlaces ya enviados.
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

from ..serializers import UnsubscribeSerializer


class NewsletterUnsubscribeView(APIView):
    """POST /api/v2/newsletter/unsubscribe/ — UC-NEW-02."""
    permission_classes = [AllowAny]
    # H-CICLO42-03: throttle para limitar bajas masivas/abusivas o enumeración
    # de tokens. Scope newsletter_unsubscribe (10/hour), simétrico a subscribe.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope   = 'newsletter_unsubscribe'

    @extend_schema(
        summary='Cancelar suscripción al newsletter (UC-NEW-02)',
        request=UnsubscribeSerializer,
        tags=['newsletter'],
        responses={200: None, 400: None, 404: None},
    )
    def post(self, request):
        ser = UnsubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.validated_data['token']

        try:
            signing.loads(token, salt='newsletter-unsub', max_age=30 * 86400)
        except signing.SignatureExpired:
            return Response(
                {'detail': 'Token expirado.', 'codigo_error': 'TOKEN_EXPIRED'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            raise NotFound({'detail': 'Token inválido.', 'codigo_error': 'INVALID_TOKEN'})

        sub = mm.find_by_unsubscribe_token(token)
        if not sub:
            raise NotFound({'detail': 'Token no encontrado.', 'codigo_error': 'INVALID_TOKEN'})

        mm.unsubscribe(sub)
        return Response(mm.serialize_item(sub))
