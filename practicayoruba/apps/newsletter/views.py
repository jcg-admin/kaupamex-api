"""
Views — apps.newsletter (P-13 / UC-NEW-01..04).

Public:
  POST /api/v1/newsletter/subscribe/           UC-NEW-01
  POST /api/v1/newsletter/unsubscribe/         UC-NEW-02

Admin:
  GET  /api/v1/admin/newsletter/subscribers/   UC-NEW-03
  POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/  UC-NEW-03
  POST /api/v1/admin/newsletter/campaigns/     UC-NEW-04
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import NewsletterSubscriber, NewsletterCampaign
from .serializers import (
    NewsletterSubscribeSerializer,
    NewsletterSubscriberAdminSerializer,
    NewsletterCampaignSerializer,
)




class NewsletterSubscribeView(APIView):
    """POST /api/v1/newsletter/subscribe/ — UC-NEW-01."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Suscribirse al newsletter (UC-NEW-01)',
        request=NewsletterSubscribeSerializer,
        tags=['newsletter'],
        responses={201: None, 200: None},
    )
    def post(self, request):
        ser = NewsletterSubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data['email']

        sub, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={'is_active': True},
        )
        if not created:
            if sub.is_active:
                return Response(
                    {'detail': 'Ya estás suscrito.',
                     'codigo_error': 'ALREADY_SUBSCRIBED'},
                    status=200,
                )
            sub.is_active = True
            sub.save(update_fields=['is_active'])

        return Response(
            {'detail': 'Suscripción confirmada.'},
            status=status.HTTP_201_CREATED,
        )


class NewsletterUnsubscribeView(APIView):
    """POST /api/v1/newsletter/unsubscribe/ — UC-NEW-02."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Cancelar suscripción al newsletter (UC-NEW-02)',
        request=NewsletterSubscribeSerializer,
        tags=['newsletter'],
        responses={200: None, 404: None},
    )
    def post(self, request):
        ser = NewsletterSubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data['email']

        try:
            sub = NewsletterSubscriber.objects.get(email=email)
        except NewsletterSubscriber.DoesNotExist:
            raise NotFound({'detail': 'Email no encontrado.',
                            'codigo_error': 'EMAIL_NOT_FOUND'})

        sub.is_active = False
        sub.save(update_fields=['is_active'])
        return Response({'detail': 'Suscripción cancelada.'})


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminSubscriberListView(_AdminOnly, APIView):
    """GET /api/v1/admin/newsletter/subscribers/ — UC-NEW-03."""

    @extend_schema(
        summary='Listar suscriptores (UC-NEW-03)',
        tags=['newsletter'],
        responses={200: NewsletterSubscriberAdminSerializer(many=True)},
    )
    def get(self, request):
        qs = NewsletterSubscriber.objects.all().order_by('-created_at')
        active = request.query_params.get('active')
        if active is not None:
            qs = qs.filter(is_active=(active.lower() == 'true'))
        return Response(NewsletterSubscriberAdminSerializer(qs, many=True).data)


class AdminSubscriberForceUnsubscribeView(_AdminOnly, APIView):
    """POST /api/v1/admin/newsletter/subscribers/<id>/unsubscribe/ — UC-NEW-03."""

    @extend_schema(
        summary='Dar de baja suscriptor (admin) (UC-NEW-03)',
        tags=['newsletter'],
        responses={200: None, 404: None},
    )
    def post(self, request, pk):
        try:
            sub = NewsletterSubscriber.objects.get(pk=pk)
        except NewsletterSubscriber.DoesNotExist:
            raise NotFound({'detail': 'Suscriptor no encontrado.',
                            'codigo_error': 'SUBSCRIBER_NOT_FOUND'})
        sub.is_active = False
        sub.save(update_fields=['is_active'])
        return Response({'detail': 'Suscriptor dado de baja.'})


class AdminCampaignCreateView(_AdminOnly, APIView):
    """POST /api/v1/admin/newsletter/campaigns/ — UC-NEW-04."""

    @extend_schema(
        summary='Crear campaña de newsletter (UC-NEW-04)',
        request=NewsletterCampaignSerializer,
        tags=['newsletter'],
        responses={201: NewsletterCampaignSerializer, 400: None},
    )
    def post(self, request):
        ser = NewsletterCampaignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        campaign = ser.save(created_by=request.user)
        return Response(
            NewsletterCampaignSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )
