"""
Views — apps.newsletter (UC-NEW-01..04).

Public endpoints:
  POST /api/v1/newsletter/subscribe/                       subscribe (doble opt-in GDPR)
  POST /api/v1/newsletter/confirm/<token>/                 confirmar suscripcion
  POST /api/v1/newsletter/unsubscribe/                     unsub via signed token

Admin endpoints:
  GET  /api/v1/admin/newsletter/subscribers/               list
  POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/  forced unsub
  POST /api/v1/admin/newsletter/campaigns/                 create + send campaign

JSON keys + identifiers in English (DEC-DOC-005).
"""
from django.conf import settings
from django.core import signing
from apps.core.email_executor import dispatch_email
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiTypes
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import NewsletterCampaign, NewsletterSubscriber, SubscriberStatus
from .serializers import CampaignCreateSerializer, CampaignResponseSerializer, SubscribeSerializer, SubscriberListItemSerializer, UnsubscribeSerializer



# ── public ────────────────────────────────────────────────────────────
class NewsletterSubscribeView(APIView):
    """POST /api/v1/newsletter/subscribe/."""

    permission_classes = [AllowAny]
    serializer_class = SubscribeSerializer

    @extend_schema(
        summary='Suscribirse a la newsletter',
        tags=['newsletter'],
        request=SubscribeSerializer,
        responses={201: OpenApiTypes.OBJECT, 200: OpenApiTypes.OBJECT},
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

        # Doble opt-in GDPR: generar token y enviar email de confirmacion (DEC-NEW-01 T-117).
        if subscriber.status == SubscriberStatus.PENDING:
            confirm_token = signing.dumps(email, salt='newsletter-confirm')
            subscriber.confirmation_token = confirm_token
            subscriber.save(update_fields=['confirmation_token', 'updated_at'])

            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3001')
            confirm_url = f'{frontend_url}/newsletter/confirm/?token={confirm_token}'
            dispatch_email(
                subject='Confirma tu suscripcion a la newsletter',
                message=(
                    f'Hola,\n\n'
                    f'Para completar tu suscripcion haz clic en el siguiente enlace:\n\n'
                    f'{confirm_url}\n\n'
                    f'El enlace expira en 24 horas.\n\n'
                    f'Si no solicitaste esta suscripcion, ignora este mensaje.'
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx'),
                recipient_list=[email],
            )

        return Response(
            {
                'id': subscriber.pk,
                'email': subscriber.email,
                'status': subscriber.status,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class NewsletterConfirmView(APIView):
    """POST /api/v1/newsletter/confirm/<token>/ — UC-NEW-01 doble opt-in (DEC-NEW-01 T-117)."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary='Confirmar suscripcion via token',
        tags=['newsletter'],
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    )
    def post(self, request, token):
        try:
            email = signing.loads(token, salt='newsletter-confirm', max_age=24 * 3600)
        except signing.SignatureExpired:
            return Response(
                {'error_code': 'TOKEN_EXPIRED', 'detail': 'Token de confirmacion expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            return Response(
                {'error_code': 'INVALID_TOKEN', 'detail': 'Token de confirmacion invalido.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            subscriber = NewsletterSubscriber.objects.get(
                email=email,
                confirmation_token=token,
            )
        except NewsletterSubscriber.DoesNotExist:
            return Response(
                {'error_code': 'INVALID_TOKEN', 'detail': 'Token de confirmacion invalido.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if subscriber.status != SubscriberStatus.CONFIRMED:
            subscriber.status = SubscriberStatus.CONFIRMED
            subscriber.confirmed_at = timezone.now()
            subscriber.confirmation_token = None
            subscriber.save(update_fields=[
                'status', 'confirmed_at', 'confirmation_token', 'updated_at',
            ])

        return Response({
            'id': subscriber.pk,
            'email': subscriber.email,
            'status': subscriber.status,
        })


class NewsletterUnsubscribeView(APIView):
    """POST /api/v1/newsletter/unsubscribe/."""

    permission_classes = [AllowAny]
    serializer_class = UnsubscribeSerializer

    @extend_schema(
        summary='Cancelar suscripcion via token',
        tags=['newsletter'],
        request=UnsubscribeSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT},
    )
    def post(self, request):
        serializer = UnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']

        # Verificar firma HMAC y TTL antes de lookup en BD (DEC-NEW-02 T-117).
        try:
            signing.loads(token, salt='newsletter-unsub', max_age=30 * 24 * 3600)
        except signing.SignatureExpired:
            return Response(
                {'error_code': 'TOKEN_EXPIRED', 'detail': 'Token expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            return Response(
                {'error_code': 'INVALID_TOKEN', 'detail': 'Token invalido.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            subscriber = NewsletterSubscriber.objects.get(
                unsubscribe_token=token,
            )
        except NewsletterSubscriber.DoesNotExist:
            return Response(
                {'error_code': 'INVALID_TOKEN', 'detail': 'Token invalido.'},
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
    serializer_class = SubscriberListItemSerializer

    @extend_schema(
        summary='Forzar baja de un suscriptor',
        tags=['newsletter'],
        responses={200: OpenApiTypes.OBJECT},
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
            dispatch_email(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx'),
                recipient_list=recipients,
            )

        return Response(
            CampaignResponseSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )
