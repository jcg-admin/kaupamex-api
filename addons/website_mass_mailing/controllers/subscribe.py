"""``NewsletterSubscribeView`` — alta pública a la newsletter (UC-NEW-01).

POST /api/v2/newsletter/subscriptions/. Persistencia delegada en
``mass_mailing.services`` (lista canónica ``"Newsletter"``). El estado
PENDING/CONFIRMED/UNSUBSCRIBED se deriva de la máquina por-lista; el salt
``newsletter-confirm`` se conserva (enlaces ya enviados / datos migrados).
"""
from django.conf import settings
from django.core import mail, signing
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from addons.base.models import CompanySetting
from addons.mass_mailing import services as mm

from .serializers import SubscribeSerializer

# Buzón de newsletter — L3 per-empresa (SOL-090 slice 3, CompanySetting). La
# constante es el fallback **neutral** (nivel Kaupamex, no Kaupamex) que
# usa ``get_setting`` cuando no hay empresa en contexto o la empresa activa no
# fijó su propio buzón — cierra H-CFG-IMPL-10.
NEWSLETTER_FROM_EMAIL_DEFAULT = 'newsletter@kaupamex.com'


def _send_confirmation_email(email: str, token: str) -> None:
    """Send double opt-in confirmation email."""
    frontend = getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')
    confirm_url = f'{frontend}/confirmar-newsletter/{token}/'
    mail.send_mail(
        subject='Confirma tu suscripción al Newsletter',
        message=f'Haz click para confirmar: {confirm_url}',
        from_email=CompanySetting.get_setting(
            'newsletter.from_email', NEWSLETTER_FROM_EMAIL_DEFAULT,
        ),
        recipient_list=[email],
        fail_silently=True,
    )


class NewsletterSubscribeView(APIView):
    """POST /api/v2/newsletter/subscriptions/ — UC-NEW-01."""
    permission_classes = [AllowAny]
    # H-CICLO26-02: throttle para evitar flooding de suscripciones y envíos
    # masivos de emails de confirmación desde una IP.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'newsletter_subscribe'

    @extend_schema(
        summary='Suscribirse al newsletter (UC-NEW-01)',
        request=SubscribeSerializer,
        tags=['newsletter'],
        responses={201: None, 200: None},
    )
    def post(self, request):
        ser = SubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data['email']

        sub = mm.find_by_email(email)
        if sub is not None:
            if mm.status_of(sub) == mm.STATUS_UNSUBSCRIBED:
                # Re-opt-in: reset to PENDING + nuevo token de confirmación.
                confirm_token = signing.dumps(email, salt='newsletter-confirm')
                mm.reopt_in(sub, confirm_token)
                _send_confirmation_email(email, confirm_token)
                return Response(mm.serialize_item(sub), status=status.HTTP_200_OK)
            # Ya suscrito (PENDING o CONFIRMED) — idempotente.
            return Response(mm.serialize_item(sub), status=status.HTTP_200_OK)

        confirm_token = signing.dumps(email, salt='newsletter-confirm')
        sub = mm.create_pending(email, confirm_token)
        _send_confirmation_email(email, confirm_token)
        return Response(mm.serialize_item(sub), status=status.HTTP_201_CREATED)
