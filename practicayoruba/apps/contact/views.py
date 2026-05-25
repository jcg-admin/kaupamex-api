"""
Views — apps.contact (P-09 / UC-COM-01..03).

Public:
  POST /api/v1/contact/  — UC-COM-01 submit message.

Admin:
  GET  /api/v1/admin/contact/                 — UC-COM-02 list messages.
  GET  /api/v1/admin/contact/<id>/            — UC-COM-03 detail.
  POST /api/v1/admin/contact/<id>/mark-read/  — UC-COM-03 mark read.
  POST /api/v1/admin/contact/<id>/reply/      — UC-COM-03 reply via email.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from apps.core.email_executor import dispatch_email
from .models import ContactMessage
from .serializers import ContactMessageSerializer, ContactMessageAdminSerializer


def _get_message(message_id):
    try:
        return ContactMessage.objects.get(pk=message_id)
    except ContactMessage.DoesNotExist:
        raise NotFound({
            'detail': 'Mensaje no encontrado.',
            'codigo_error': 'MESSAGE_NOT_FOUND',
        })


class ContactMessageCreateView(APIView):
    """POST /api/v1/contact/ — UC-COM-01."""
    permission_classes = [AllowAny]
    # H-CICLO26-01: throttle_scope sin throttle_classes es silenciosamente
    # ignorado por DRF — ScopedRateThrottle es quien lee el scope y aplica
    # el rate configurado en DEFAULT_THROTTLE_RATES['contact'] = '5/hour'.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'contact'

    @extend_schema(
        summary='Enviar mensaje de contacto (UC-COM-01)',
        request=ContactMessageSerializer,
        tags=['contact'],
        responses={201: ContactMessageSerializer},
    )
    def post(self, request):
        ser = ContactMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        msg = ser.save()
        return Response(ContactMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminContactMessageListView(_AdminOnly, APIView):
    """GET /api/v1/admin/contact/ — UC-COM-02."""

    @extend_schema(
        summary='Listar mensajes de contacto (UC-COM-02)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer(many=True)},
    )
    def get(self, request):
        qs = ContactMessage.objects.all().order_by('-created_at')
        return Response({'results': ContactMessageAdminSerializer(qs, many=True).data})


class AdminContactMessageDetailView(_AdminOnly, APIView):
    """GET /api/v1/admin/contact/<id>/ — UC-COM-03 detail."""

    @extend_schema(
        summary='Detalle de mensaje de contacto (UC-COM-03)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer, 404: None},
    )
    def get(self, request, message_id):
        msg = _get_message(message_id)
        return Response(ContactMessageAdminSerializer(msg).data)


class AdminContactMessageMarkReadView(_AdminOnly, APIView):
    """POST /api/v1/admin/contact/<id>/mark-read/ — UC-COM-03."""

    @extend_schema(
        summary='Marcar mensaje como leído (UC-COM-03)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer, 404: None},
    )
    def post(self, request, message_id):
        msg = _get_message(message_id)
        msg.read = True
        msg.save(update_fields=['read', 'updated_at'])
        return Response(ContactMessageAdminSerializer(msg).data)


class AdminContactMessageReplyView(_AdminOnly, APIView):
    """POST /api/v1/admin/contact/<id>/reply/ — UC-COM-03 reply via email."""

    @extend_schema(
        summary='Responder mensaje de contacto por email (UC-COM-03)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer, 400: None, 404: None},
    )
    def post(self, request, message_id):
        reply_body = (request.data.get('reply_body') or '').strip()
        if not reply_body:
            raise ValidationError({
                'detail': 'El cuerpo de la respuesta es requerido.',
                'codigo_error': 'BODY_REQUIRED',
            })

        with transaction.atomic():
            try:
                msg = ContactMessage.objects.select_for_update().get(pk=message_id)
            except ContactMessage.DoesNotExist:
                raise NotFound({
                    'detail': 'Mensaje no encontrado.',
                    'codigo_error': 'MESSAGE_NOT_FOUND',
                })

            if msg.replied:
                return Response(
                    {
                        'detail': 'El mensaje ya fue respondido.',
                        'codigo_error': 'MESSAGE_ALREADY_REPLIED',
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            msg.read = True
            msg.replied = True
            msg.reply_body = reply_body
            msg.reply_sent_at = timezone.now()
            msg.save(update_fields=['read', 'replied', 'reply_body', 'reply_sent_at', 'updated_at'])

        dispatch_email(
            subject=f'Re: {msg.subject}',
            message=reply_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[msg.email],
        )

        return Response(ContactMessageAdminSerializer(msg).data)
