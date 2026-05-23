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
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.email_executor import dispatch_email
from .models import ContactMessage
from .serializers import ContactMessageSerializer, ContactMessageAdminSerializer




class ContactMessageCreateView(APIView):
    """POST /api/v1/contact/ — UC-COM-01."""
    permission_classes = [AllowAny]

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
        return Response(ContactMessageAdminSerializer(qs, many=True).data)


class AdminContactMessageDetailView(_AdminOnly, APIView):
    """GET /api/v1/admin/contact/<id>/ — UC-COM-03 detail."""

    @extend_schema(
        summary='Detalle de mensaje de contacto (UC-COM-03)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer, 404: None},
    )
    def get(self, request, pk):
        try:
            msg = ContactMessage.objects.get(pk=pk)
        except ContactMessage.DoesNotExist:
            raise NotFound({
                'detail': 'Mensaje no encontrado.',
                'codigo_error': 'MESSAGE_NOT_FOUND',
            })
        return Response(ContactMessageAdminSerializer(msg).data)


class AdminContactMessageMarkReadView(_AdminOnly, APIView):
    """POST /api/v1/admin/contact/<id>/mark-read/ — UC-COM-03."""

    @extend_schema(
        summary='Marcar mensaje como leído (UC-COM-03)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer, 404: None},
    )
    def post(self, request, pk):
        try:
            msg = ContactMessage.objects.get(pk=pk)
        except ContactMessage.DoesNotExist:
            raise NotFound({
                'detail': 'Mensaje no encontrado.',
                'codigo_error': 'MESSAGE_NOT_FOUND',
            })
        msg.is_read = True
        msg.save(update_fields=['is_read'])
        return Response(ContactMessageAdminSerializer(msg).data)


class AdminContactMessageReplyView(_AdminOnly, APIView):
    """POST /api/v1/admin/contact/<id>/reply/ — UC-COM-03 reply via email."""

    @extend_schema(
        summary='Responder mensaje de contacto por email (UC-COM-03)',
        tags=['contact'],
        responses={200: None, 400: None, 404: None},
    )
    def post(self, request, pk):
        try:
            msg = ContactMessage.objects.get(pk=pk)
        except ContactMessage.DoesNotExist:
            raise NotFound({
                'detail': 'Mensaje no encontrado.',
                'codigo_error': 'MESSAGE_NOT_FOUND',
            })

        reply_body = (request.data.get('reply_body') or '').strip()
        if not reply_body:
            return Response(
                {'detail': 'El cuerpo de la respuesta es requerido.',
                 'codigo_error': 'BODY_REQUIRED'},
                status=400,
            )

        dispatch_email(
            subject=f'Re: {msg.subject}',
            message=reply_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[msg.email],
        )

        msg.is_read = True
        msg.save(update_fields=['is_read'])

        return Response({'detail': 'Respuesta enviada.'})
