"""
Views — apps.contact (UC-COM-01..03).

Public endpoints:
  POST /api/v1/contact/messages/                          create message

Admin endpoints:
  GET  /api/v1/admin/contact/messages/                    inbox
  GET  /api/v1/admin/contact/messages/<id>/               detail
  POST /api/v1/admin/contact/messages/<id>/read/          mark as read
  POST /api/v1/admin/contact/messages/<id>/reply/         send reply

JSON keys + identifiers in English (DEC-DOC-005).
"""
from apps.core.email_executor import dispatch_email
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.conf import settings
from .models import ContactMessage
from .serializers import ContactMessageCreateSerializer, ContactMessageListItemSerializer, ContactMessageReplySerializer




class ContactMessageCreateView(APIView):
    """POST /api/v1/contact/messages/ — public submission."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'contact'

    @extend_schema(
        summary='Enviar mensaje de contacto',
        tags=['contact'],
        request=ContactMessageCreateSerializer,
        responses={201: ContactMessageListItemSerializer},
    )
    def post(self, request):
        serializer = ContactMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ContactMessage.objects.create(**serializer.validated_data)
        return Response(
            ContactMessageListItemSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )


class AdminContactMessageListView(APIView):
    """GET /api/v1/admin/contact/messages/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Listar mensajes de contacto',
        tags=['contact'],
        responses=ContactMessageListItemSerializer(many=True),
    )
    def get(self, request):
        qs = ContactMessage.objects.all()
        # status filter: sin_leer | leido | respondido (DEC-COM-01 T-117).
        status_param = request.query_params.get('status')
        if status_param == 'sin_leer':
            qs = qs.filter(read=False)
        elif status_param == 'leido':
            qs = qs.filter(read=True, replied=False)
        elif status_param == 'respondido':
            qs = qs.filter(replied=True)
        data = ContactMessageListItemSerializer(qs, many=True).data
        return Response({'results': data})


class AdminContactMessageDetailView(APIView):
    """GET /api/v1/admin/contact/messages/<id>/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Detalle de mensaje de contacto',
        tags=['contact'],
        responses=ContactMessageListItemSerializer,
    )
    def get(self, request, message_id):
        message = get_object_or_404(ContactMessage, pk=message_id)
        # Auto-mark-read on detail access (DEC-COM-02 T-117).
        if not message.read:
            message.read = True
            message.save(update_fields=['read', 'updated_at'])
        return Response(ContactMessageListItemSerializer(message).data)


class AdminContactMessageMarkReadView(APIView):
    """POST /api/v1/admin/contact/messages/<id>/read/."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ContactMessageListItemSerializer

    @extend_schema(
        summary='Marcar mensaje como leido',
        request=None,
        responses={200: OpenApiResponse(description='Marcado como leido.')},
        tags=['contact'],
    )
    def post(self, request, message_id):
        message = get_object_or_404(ContactMessage, pk=message_id)
        if not message.read:
            message.read = True
            message.save(update_fields=['read', 'updated_at'])
        return Response({'id': message.pk, 'read': True})


class AdminContactMessageReplyView(APIView):
    """POST /api/v1/admin/contact/messages/<id>/reply/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Responder mensaje de contacto',
        tags=['contact'],
        request=ContactMessageReplySerializer,
        responses=ContactMessageListItemSerializer,
    )
    def post(self, request, message_id):
        message = get_object_or_404(ContactMessage, pk=message_id)

        # Idempotency: if already replied, return current state without re-sending email.
        if message.replied:
            return Response(
                ContactMessageListItemSerializer(message).data,
                status=status.HTTP_200_OK,
            )

        serializer = ContactMessageReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply_body = serializer.validated_data['reply_body']

        dispatch_email(
            subject=f'Re: {message.subject}',
            message=reply_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@practicayoruba.mx'),
            recipient_list=[message.email],
        )

        message.reply_body = reply_body
        message.reply_sent_at = timezone.now()
        message.reply_sent_by = request.user
        message.replied = True
        if not message.read:
            message.read = True
        message.save(update_fields=[
            'reply_body', 'reply_sent_at', 'reply_sent_by',
            'replied', 'read', 'updated_at',
        ])
        return Response(ContactMessageListItemSerializer(message).data)
