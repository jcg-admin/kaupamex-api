"""
Views — apps.newsletter (UC-NEW-01..04).

Public endpoints:
  POST /api/v1/newsletter/subscribe/                       subscribe (double opt-in optional)
  POST /api/v1/newsletter/unsubscribe/                     unsub via signed token

Admin endpoints:
  GET  /api/v1/admin/newsletter/subscribers/               list
  POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/  forced unsub
  POST /api/v1/admin/newsletter/campaigns/                 create + send campaign

JSON keys + identifiers in English (DEC-DOC-005).
"""
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    NewsletterCampaign,
    NewsletterSubscriber,
    SubscriberStatus,
)
from .serializers import (
    CampaignCreateSerializer,
    CampaignResponseSerializer,
    SubscribeSerializer,
    SubscriberListItemSerializer,
    UnsubscribeSerializer,
)


# ── public ────────────────────────────────────────────────────────────
class NewsletterSubscribeView(APIView):
    """POST /api/v1/newsletter/subscribe/."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary='Suscribirse a la newsletter',
        tags=['newsletter'],
        request=SubscribeSerializer,
    )
    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={'status': SubscriberStatus.PENDING},
        )

        # Si ya existia en CONFIRMED, lo dejamos asi; si estaba UNSUBSCRIBED,
        # volvemos a PENDING (re-opt-in con doble confirmacion).
        if not created and subscriber.status == SubscriberStatus.UNSUBSCRIBED:
            subscriber.status = SubscriberStatus.PENDING
            subscriber.unsubscribed_at = None
            subscriber.save(update_fields=[
                'status', 'unsubscribed_at', 'updated_at',
            ])

        return Response(
            {
                'id': subscriber.pk,
                'email': subscriber.email,
                'status': subscriber.status,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class NewsletterUnsubscribeView(APIView):
    """POST /api/v1/newsletter/unsubscribe/."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary='Cancelar suscripcion via token',
        tags=['newsletter'],
        request=UnsubscribeSerializer,
    )
    def post(self, request):
        serializer = UnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']

        try:
            subscriber = NewsletterSubscriber.objects.get(
                unsubscribe_token=token,
            )
        except NewsletterSubscriber.DoesNotExist:
            return Response(
                {'error_code': 'INVALID_TOKEN',
                 'detail': 'Token invalido.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if subscriber.status != SubscriberStatus.UNSUBSCRIBED:
            subscriber.status = SubscriberStatus.UNSUBSCRIBED
            subscriber.unsubscribed_at = timezone.now()
            subscriber.save(update_fields=[
                'status', 'unsubscribed_at', 'updated_at',
            ])

        return Response({
            'id': subscriber.pk,
            'email': subscriber.email,
            'status': subscriber.status,
        })


# ── admin ─────────────────────────────────────────────────────────────
class AdminSubscriberListView(APIView):
    """GET /api/v1/admin/newsletter/subscribers/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Listar suscriptores',
        tags=['newsletter'],
        responses=SubscriberListItemSerializer(many=True),
    )
    def get(self, request):
        qs = NewsletterSubscriber.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        data = SubscriberListItemSerializer(qs, many=True).data
        return Response({'results': data})


class AdminSubscriberForceUnsubscribeView(APIView):
    """POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Forzar baja de un suscriptor',
        tags=['newsletter'],
    )
    def post(self, request, subscriber_id):
        subscriber = get_object_or_404(NewsletterSubscriber, pk=subscriber_id)
        if subscriber.status != SubscriberStatus.UNSUBSCRIBED:
            subscriber.status = SubscriberStatus.UNSUBSCRIBED
            subscriber.unsubscribed_at = timezone.now()
            subscriber.save(update_fields=[
                'status', 'unsubscribed_at', 'updated_at',
            ])
        return Response({
            'id': subscriber.pk,
            'email': subscriber.email,
            'status': subscriber.status,
        })


class AdminCampaignCreateView(APIView):
    """POST /api/v1/admin/newsletter/campaigns/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Crear y enviar campana',
        tags=['newsletter'],
        request=CampaignCreateSerializer,
        responses={201: CampaignResponseSerializer},
    )
    def post(self, request):
        serializer = CampaignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        audience_filter = payload.get(
            'audience_filter', SubscriberStatus.CONFIRMED,
        )
        subject = payload['subject']
        body = payload['body']

        recipients = list(
            NewsletterSubscriber.objects
            .filter(status=audience_filter)
            .values_list('email', flat=True)
        )

        with transaction.atomic():
            campaign = NewsletterCampaign.objects.create(
                sender=request.user,
                subject=subject,
                body=body,
                audience_filter=audience_filter,
                sent_at=timezone.now(),
                recipients_count=len(recipients),
            )

        if recipients:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(
                    settings, 'DEFAULT_FROM_EMAIL',
                    'noreply@practicayoruba.mx',
                ),
                recipient_list=recipients,
                fail_silently=True,
            )

        return Response(
            CampaignResponseSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )
