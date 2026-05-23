"""
Views — apps.newsletter (P-13 / UC-NEW-01..04).

Public:
  POST /api/v1/newsletter/subscribe/           UC-NEW-01
  POST /api/v1/newsletter/confirm/<token>/     UC-NEW-01 (doble opt-in, DEC-NEW-01)
  POST /api/v1/newsletter/unsubscribe/         UC-NEW-02 (DEC-NEW-02)

Admin:
  GET  /api/v1/admin/newsletter/subscribers/   UC-NEW-03
  POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/  UC-NEW-03
  POST /api/v1/admin/newsletter/campaigns/     UC-NEW-04
"""
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.email_executor import dispatch_email
from .models import NewsletterCampaign, NewsletterSubscriber, SubscriberStatus
from .serializers import (
    CampaignCreateSerializer,
    CampaignResponseSerializer,
    SubscribeSerializer,
    SubscriberListItemSerializer,
    UnsubscribeSerializer,
)

_CONFIRM_SALT = 'newsletter-confirm'
_CONFIRM_TTL  = 24 * 3600        # D-01: 24-hour window for double opt-in
_UNSUB_SALT   = 'newsletter-unsub'
_UNSUB_TTL    = 30 * 24 * 3600   # D-02: 30-day TTL for unsubscribe links


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


# ─── Public ───────────────────────────────────────────────────────────────────────

class NewsletterSubscribeView(APIView):
    """POST /api/v1/newsletter/subscribe/ — UC-NEW-01."""
    permission_classes = [AllowAny]

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

        sub, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={'status': SubscriberStatus.PENDING},
        )

        # Confirmed subscriber re-subscribes: idempotent, no new token.
        if not created and sub.status == SubscriberStatus.CONFIRMED:
            return Response({'email': sub.email, 'status': sub.status}, status=200)

        # New subscriber or re-opt-in (PENDING / UNSUBSCRIBED).
        # D-01: generate TimestampSigner token (24h TTL) for double opt-in.
        token = signing.dumps(email, salt=_CONFIRM_SALT)
        sub.status = SubscriberStatus.PENDING
        sub.confirmation_token = token
        sub.save(update_fields=['status', 'confirmation_token', 'updated_at'])

        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')
        confirm_url  = f'{frontend_url}/newsletter/confirmar/?token={token}'
        dispatch_email(
            subject='Confirma tu suscripción a PracticaYoruba',
            message=(
                f'Haz clic en el siguiente enlace para confirmar tu suscripción\n\n'
                f'{confirm_url}\n\nEste enlace caduca en 24 horas.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx'),
            recipient_list=[email],
        )

        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({'email': sub.email, 'status': sub.status}, status=http_status)


class NewsletterConfirmView(APIView):
    """POST /api/v1/newsletter/confirm/<token>/ — doble opt-in UC-NEW-01 (DEC-NEW-01)."""
    permission_classes = [AllowAny]

    def post(self, request, token):
        # Verify HMAC signature and 24h TTL before DB lookup.
        try:
            email = signing.loads(token, salt=_CONFIRM_SALT, max_age=_CONFIRM_TTL)
        except signing.SignatureExpired:
            return Response({'error_code': 'TOKEN_EXPIRED'}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({'error_code': 'INVALID_TOKEN'}, status=status.HTTP_404_NOT_FOUND)

        sub = NewsletterSubscriber.objects.filter(
            email=email,
            confirmation_token=token,
        ).first()
        if not sub:
            return Response({'error_code': 'INVALID_TOKEN'}, status=status.HTTP_404_NOT_FOUND)

        sub.status           = SubscriberStatus.CONFIRMED
        sub.confirmed_at     = timezone.now()
        sub.confirmation_token = None
        sub.save(update_fields=['status', 'confirmed_at', 'confirmation_token', 'updated_at'])
        return Response({'email': sub.email, 'status': sub.status})


class NewsletterUnsubscribeView(APIView):
    """POST /api/v1/newsletter/unsubscribe/ — UC-NEW-02 (DEC-NEW-02)."""
    permission_classes = [AllowAny]

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

        # D-02: verify HMAC signature + 30-day TTL before touching the DB.
        try:
            signing.loads(token, salt=_UNSUB_SALT, max_age=_UNSUB_TTL)
        except signing.SignatureExpired:
            return Response({'error_code': 'TOKEN_EXPIRED'}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({'error_code': 'INVALID_TOKEN'}, status=status.HTTP_404_NOT_FOUND)

        sub = NewsletterSubscriber.objects.filter(unsubscribe_token=token).first()
        if not sub:
            return Response({'error_code': 'INVALID_TOKEN'}, status=status.HTTP_404_NOT_FOUND)

        sub.status          = SubscriberStatus.UNSUBSCRIBED
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=['status', 'unsubscribed_at', 'updated_at'])
        return Response({'status': sub.status})


# ─── Admin ─────────────────────────────────────────────────────────────────────────


class _SubscriberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminSubscriberListView(_AdminOnly, APIView):
    """GET /api/v1/admin/newsletter/subscribers/ — UC-NEW-03."""

    @extend_schema(
        summary='Listar suscriptores (UC-NEW-03)',
        tags=['newsletter'],
        responses={200: SubscriberListItemSerializer(many=True)},
    )
    def get(self, request):
        qs = NewsletterSubscriber.objects.order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        paginator = _SubscriberPagination()
        page      = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            SubscriberListItemSerializer(page, many=True).data
        )


class AdminSubscriberForceUnsubscribeView(_AdminOnly, APIView):
    """POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/ — UC-NEW-03."""

    @extend_schema(
        summary='Dar de baja suscriptor (admin) (UC-NEW-03)',
        tags=['newsletter'],
        responses={200: None, 404: None},
    )
    def post(self, request, pk):
        sub = NewsletterSubscriber.objects.filter(pk=pk).first()
        if not sub:
            raise NotFound({'detail': 'Suscriptor no encontrado.',
                            'error_code': 'SUBSCRIBER_NOT_FOUND'})
        sub.status          = SubscriberStatus.UNSUBSCRIBED
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=['status', 'unsubscribed_at', 'updated_at'])
        return Response({'status': sub.status})


class AdminCampaignCreateView(_AdminOnly, APIView):
    """POST /api/v1/admin/newsletter/campaigns/ — UC-NEW-04."""

    @extend_schema(
        summary='Crear campaña de newsletter (UC-NEW-04)',
        request=CampaignCreateSerializer,
        tags=['newsletter'],
        responses={201: CampaignResponseSerializer, 400: None},
    )
    def post(self, request):
        ser = CampaignCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        subject         = ser.validated_data['subject']
        body            = ser.validated_data['body']
        audience_filter = ser.validated_data.get('audience_filter', SubscriberStatus.CONFIRMED)

        recipients = list(
            NewsletterSubscriber.objects
            .filter(status=audience_filter)
            .values_list('email', flat=True)
        )

        campaign = NewsletterCampaign.objects.create(
            sender=request.user,
            subject=subject,
            body=body,
            audience_filter=audience_filter,
            recipients_count=len(recipients),
            sent_at=timezone.now(),
        )

        if recipients:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx'),
                recipient_list=recipients,
            )

        return Response(
            CampaignResponseSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )
