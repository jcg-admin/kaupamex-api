"""
Views — apps.newsletter (P-13 / UC-NEW-01..04).

Public:
  POST /api/v1/newsletter/subscribe/           UC-NEW-01
  POST /api/v1/newsletter/confirm/<token>/     UC-NEW-01 double opt-in
  POST /api/v1/newsletter/unsubscribe/         UC-NEW-02

Admin:
  GET  /api/v1/admin/newsletter/subscribers/                         UC-NEW-03
  POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/        UC-NEW-03
  POST /api/v1/admin/newsletter/campaigns/                           UC-NEW-04
"""
from datetime import timedelta

from django.core import mail, signing
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import NewsletterCampaign, NewsletterSubscriber, SubscriberStatus
from .serializers import (
    CampaignCreateSerializer,
    CampaignResponseSerializer,
    SubscribeSerializer,
    SubscriberListItemSerializer,
    UnsubscribeSerializer,
)


class NewsletterSubscribeView(APIView):
    """POST /api/v1/newsletter/subscribe/ — UC-NEW-01."""
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

        try:
            sub = NewsletterSubscriber.objects.get(email=email)
            # Existing subscriber
            if sub.status == SubscriberStatus.UNSUBSCRIBED:
                # Re-opt-in: reset to PENDING
                confirm_token = signing.dumps(email, salt='newsletter-confirm')
                sub.status = SubscriberStatus.PENDING
                sub.confirmation_token = confirm_token
                sub.unsubscribed_at = None
                sub.save(update_fields=['status', 'confirmation_token', 'unsubscribed_at', 'updated_at'])
                _send_confirmation_email(email, confirm_token)
                return Response(
                    SubscriberListItemSerializer(sub).data,
                    status=status.HTTP_200_OK,
                )
            else:
                # Already subscribed (PENDING or CONFIRMED)
                return Response(
                    SubscriberListItemSerializer(sub).data,
                    status=status.HTTP_200_OK,
                )
        except NewsletterSubscriber.DoesNotExist:
            confirm_token = signing.dumps(email, salt='newsletter-confirm')
            sub = NewsletterSubscriber.objects.create(
                email=email,
                status=SubscriberStatus.PENDING,
                confirmation_token=confirm_token,
            )
            _send_confirmation_email(email, confirm_token)
            return Response(
                SubscriberListItemSerializer(sub).data,
                status=status.HTTP_201_CREATED,
            )


def _send_confirmation_email(email: str, token: str) -> None:
    """Send double opt-in confirmation email."""
    confirm_url = f'https://practicayoruba.mx/confirmar-newsletter/{token}/'
    mail.send_mail(
        subject='Confirma tu suscripción al Newsletter',
        message=f'Haz click para confirmar: {confirm_url}',
        from_email='newsletter@practicayoruba.mx',
        recipient_list=[email],
        fail_silently=True,
    )


class NewsletterConfirmView(APIView):
    """POST /api/v1/newsletter/confirm/<token>/ — UC-NEW-01 double opt-in."""
    permission_classes = [AllowAny]
    # H-CICLO26-02: throttle para limitar intentos de fuerza bruta sobre tokens.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'newsletter_confirm'

    @extend_schema(
        summary='Confirmar suscripción al newsletter (UC-NEW-01)',
        tags=['newsletter'],
        responses={200: None, 400: None, 404: None},
    )
    def post(self, request, token):
        # Validate token signature
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

        # Token is valid; find subscriber by confirmation_token
        sub = NewsletterSubscriber.objects.filter(
            email=email, confirmation_token=token,
        ).first()
        if not sub:
            raise NotFound({'detail': 'Token no encontrado.', 'codigo_error': 'INVALID_TOKEN'})

        sub.status = SubscriberStatus.CONFIRMED
        sub.confirmed_at = timezone.now()
        sub.confirmation_token = None
        sub.save(update_fields=['status', 'confirmed_at', 'confirmation_token', 'updated_at'])

        return Response(SubscriberListItemSerializer(sub).data)


class NewsletterUnsubscribeView(APIView):
    """POST /api/v1/newsletter/unsubscribe/ — UC-NEW-02."""
    permission_classes = [AllowAny]
    # H-CICLO42-03: throttle para limitar intentos de baja masiva/abusiva
    # o enumeracion de tokens. El scope newsletter_unsubscribe (10/hour)
    # es equivalente al de subscribe para mantener la simetria de limites.
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

        # Validate token signature (30-day TTL)
        try:
            signing.loads(token, salt='newsletter-unsub', max_age=30 * 86400)
        except signing.SignatureExpired:
            return Response(
                {'detail': 'Token expirado.', 'codigo_error': 'TOKEN_EXPIRED'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            raise NotFound({'detail': 'Token inválido.', 'codigo_error': 'INVALID_TOKEN'})

        sub = NewsletterSubscriber.objects.filter(unsubscribe_token=token).first()
        if not sub:
            raise NotFound({'detail': 'Token no encontrado.', 'codigo_error': 'INVALID_TOKEN'})

        sub.status = SubscriberStatus.UNSUBSCRIBED
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=['status', 'unsubscribed_at', 'updated_at'])
        return Response(SubscriberListItemSerializer(sub).data)


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class SubscriberPagination(PageNumberPagination):
    """H-CICLO43-03: paginacion para listado admin de suscriptores.
    Sin paginacion, devolver todos los suscriptores en una sola respuesta
    puede suponer miles de filas y un timeout/OOM en produccion."""
    page_size            = 50
    page_size_query_param = 'page_size'
    max_page_size        = 200


class AdminSubscriberListView(_AdminOnly, APIView):
    """GET /api/v1/admin/newsletter/subscribers/ — UC-NEW-03."""

    @extend_schema(
        summary='Listar suscriptores (UC-NEW-03)',
        tags=['newsletter'],
        responses={200: SubscriberListItemSerializer(many=True)},
    )
    def get(self, request):
        qs = NewsletterSubscriber.objects.all().order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        paginator = SubscriberPagination()
        page = paginator.paginate_queryset(qs, request)
        serialized = SubscriberListItemSerializer(page, many=True)
        return paginator.get_paginated_response(serialized.data)


class AdminSubscriberForceUnsubscribeView(_AdminOnly, APIView):
    """POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/ — UC-NEW-03."""

    @extend_schema(
        summary='Dar de baja suscriptor (admin) (UC-NEW-03)',
        tags=['newsletter'],
        responses={200: None, 404: None},
    )
    def post(self, request, subscriber_id):
        try:
            sub = NewsletterSubscriber.objects.get(pk=subscriber_id)
        except NewsletterSubscriber.DoesNotExist:
            raise NotFound({'detail': 'Suscriptor no encontrado.',
                            'codigo_error': 'SUBSCRIBER_NOT_FOUND'})
        sub.status = SubscriberStatus.UNSUBSCRIBED
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=['status', 'unsubscribed_at', 'updated_at'])
        return Response(SubscriberListItemSerializer(sub).data)


_CAMPAIGN_DEDUP_WINDOW = timedelta(minutes=10)


class AdminCampaignCreateView(_AdminOnly, APIView):
    """POST /api/v1/admin/newsletter/campaigns/ — UC-NEW-04.

    H-CICLO78-01: guarda de idempotencia contra doble envio.
    Un segundo POST identico (mismo subject + body + audience_filter)
    dentro de la ventana de deduplicacion (_CAMPAIGN_DEDUP_WINDOW)
    retorna 409 con codigo_error CAMPAIGN_ALREADY_SENT en lugar de crear
    una segunda campana y enviar los emails de nuevo.
    La comprobacion se hace dentro de transaction.atomic() con
    select_for_update() para evitar la race condition en envios
    concurrentes desde distintos procesos WSGI.
    """

    @extend_schema(
        summary='Crear campaña de newsletter (UC-NEW-04)',
        request=CampaignCreateSerializer,
        tags=['newsletter'],
        responses={201: CampaignResponseSerializer, 400: None, 409: None},
    )
    def post(self, request):
        ser = CampaignCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vdata = ser.validated_data

        audience_filter = vdata.get('audience_filter', SubscriberStatus.CONFIRMED)
        subject = vdata['subject']
        body = vdata['body']

        with transaction.atomic():
            # H-CICLO78-01: duplicate guard — lock rows to prevent concurrent
            # double-send from multiple WSGI processes.
            cutoff = timezone.now() - _CAMPAIGN_DEDUP_WINDOW
            existing = (
                NewsletterCampaign.objects
                .select_for_update()
                .filter(
                    subject=subject,
                    body=body,
                    audience_filter=audience_filter,
                    created_at__gte=cutoff,
                )
                .first()
            )
            if existing:
                return Response(
                    {
                        'detail': (
                            'Esta campaña ya fue enviada recientemente. '
                            'Espera al menos 10 minutos antes de reenviar.'
                        ),
                        'codigo_error': 'CAMPAIGN_ALREADY_SENT',
                        'campaign_id': existing.pk,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            recipients = list(
                NewsletterSubscriber.objects.filter(status=audience_filter)
                .values_list('email', flat=True)
            )

            campaign = NewsletterCampaign.objects.create(
                sender=request.user,
                subject=subject,
                body=body,
                audience_filter=audience_filter,
                recipients_count=len(recipients),
                sent_at=timezone.now() if recipients else None,
            )

        if recipients:
            for recipient_email in recipients:
                mail.send_mail(
                    subject=campaign.subject,
                    message=campaign.body,
                    from_email='newsletter@practicayoruba.mx',
                    recipient_list=[recipient_email],
                    fail_silently=True,
                )

        return Response(
            CampaignResponseSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )
