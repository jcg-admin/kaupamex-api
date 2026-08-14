"""Controllers — formulario de contacto (``crm``, UC-COM-01..03).

Superficie restaurada del ex-addon ``contact`` (retirado en
``api@36c3416``; el modelo ``ContactMessage`` ya vivía aquí desde el fold
``api@0c2ed70``). El reparto es el de la referencia: la página
``/contactus`` es de ``website`` y su captura aterriza en el CRM vía
``website_crm`` (``odoo19c: website_crm/controllers/``, LGPL-3) — aquí la
página la renderiza React y esta API es la captura + su bandeja admin.

Public:
  POST /api/v2/contact/messages/                    Crear mensaje (anónimo).

Admin (``/api/v2/admin/contact/``):
  GET   messages/                                   Bandeja paginada.
  PATCH messages/<id>/                              Marcar leído (Tier B).
  POST  messages/<id>/read/                         Marcar leído (v1 compat).
  POST  messages/<id>/reply|replies/                Responder por correo.

Los buzones remitente/notificación son config L3 per-empresa
(``CompanySetting``, SOL-090); el fallback es neutral nivel Kaupamex.
"""
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from addons.authz.permissions import HasCapability
from addons.base.models import CompanySetting
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from addons.mail.models.email_executor import dispatch_email
from config.schema import error_response
from addons.crm.models import ContactMessage
from addons.crm.controllers.serializers import (
    ContactMessageAdminSerializer, ContactMessageReplySerializer,
    ContactMessageSerializer,
)

# Buzones de contacto — L3 per-empresa (SOL-090 slice 3, CompanySetting).
# Antes eran ``settings.CONTACT_FROM_EMAIL``/``CONTACT_NOTIFY_EMAIL`` con
# ``default=`` cableado. Ese default NO era stale — es la config L1 correcta
# del L1 de ejemplo PracticaYoruba (Kaupamex es L0, no PracticaYoruba); la
# migración ``company/0006_seed_founder_settings`` lo siembra como su propio
# ``CompanySetting``. Las constantes de abajo son el fallback **neutral**
# (nivel Kaupamex, no de PracticaYoruba) que usa ``get_setting`` cuando no
# hay empresa en contexto (request anónimo, pre resolutor subdominio→company
# UC-PLT-06) o la empresa activa no fijó su propio buzón — cierra
# H-CFG-IMPL-10.
CONTACT_FROM_EMAIL_DEFAULT = 'hola@kaupamex.com'
CONTACT_NOTIFY_EMAIL_DEFAULT = 'hola@kaupamex.com'


class _ContactMessagePagination(PageNumberPagination):
    page_size             = 25
    page_size_query_param = 'page_size'
    max_page_size         = 100


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
        # UC-COM-01: avisar al equipo en el buzón de contacto (hola@) en cuanto
        # entra un mensaje; antes el mensaje quedaba solo en el panel admin sin
        # notificación. El envío es asíncrono y reintentable (EmailTask) para no
        # bloquear la respuesta pública ni perder el aviso si el SMTP falla.
        dispatch_email(
            subject=f'Nuevo mensaje de contacto: {msg.subject}',
            message=(
                f'De: {msg.name} <{msg.email}>\n'
                f'Teléfono: {msg.phone or "—"}\n\n'
                f'{msg.body}'
            ),
            from_email=CompanySetting.get_setting(
                'contact.from_email', CONTACT_FROM_EMAIL_DEFAULT,
            ),
            recipient_list=[CompanySetting.get_setting(
                'contact.notify_email', CONTACT_NOTIFY_EMAIL_DEFAULT,
            )],
        )
        return Response(ContactMessageSerializer(msg).data, status=status.HTTP_201_CREATED)


class _AdminOnly:
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'support.edit'


class AdminContactMessageListView(_AdminOnly, APIView):
    """GET /api/v1/admin/contact/ — UC-COM-02."""

    @extend_schema(
        summary='Listar mensajes de contacto (UC-COM-02)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer(many=True)},
    )
    def get(self, request):
        qs = ContactMessage.objects.all().order_by('-created_at')
        # H-CICLO76-09: paginate to avoid OOM on large contact message tables.
        # An unbounded queryset could load thousands of rows into memory on a
        # single request.  25 per page is consistent with other admin list
        # views (AdminUserPagination, ReturnPagination).
        paginator = _ContactMessagePagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                ContactMessageAdminSerializer(page, many=True).data
            )
        return Response({'results': ContactMessageAdminSerializer(qs, many=True).data})


class AdminContactMessageDetailView(_AdminOnly, APIView):
    """GET + PATCH /api/v1/admin/contact/<id>/ — UC-COM-03 detail / mark-read."""

    @extend_schema(
        summary='Detalle de mensaje de contacto (UC-COM-03)',
        tags=['contact'],
        responses={200: ContactMessageAdminSerializer, 404: None},
    )
    def get(self, request, message_id):
        msg = _get_message(message_id)
        return Response(ContactMessageAdminSerializer(msg).data)

    @extend_schema(
        summary='Marcar mensaje como leído via PATCH (UC-COM-02)',
        tags=['contact'],
        request=None,
        responses={200: ContactMessageAdminSerializer,
                   404: error_response('Mensaje no encontrado')},
    )
    def patch(self, request, message_id):
        msg = _get_message(message_id)
        if request.data.get('is_read') is True:
            msg.read = True
            msg.save(update_fields=['read', 'updated_at'])
        return Response(ContactMessageAdminSerializer(msg).data)


class AdminContactMessageMarkReadView(_AdminOnly, APIView):
    """POST /api/v1/admin/contact/<id>/mark-read/ — UC-COM-03."""

    @extend_schema(
        summary='Marcar mensaje como leído (UC-COM-03)',
        tags=['contact'],
        request=None,
        responses={200: ContactMessageAdminSerializer,
                   404: error_response('Mensaje no encontrado')},
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
        request=ContactMessageReplySerializer,
        responses={200: ContactMessageAdminSerializer,
                   400: error_response('Cuerpo de la respuesta requerido'),
                   404: error_response('Mensaje no encontrado')},
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
            from_email=CompanySetting.get_setting(
                'contact.from_email', CONTACT_FROM_EMAIL_DEFAULT,
            ),
            recipient_list=[msg.email],
        )
        return Response(ContactMessageAdminSerializer(msg).data)


class AdminContactMessageV2View(APIView):
    """GET/PATCH /api/v2/admin/contact/messages/<id>/ — Tier B.

    GET  — return message detail (delegates to AdminContactMessageDetailView).
    PATCH — accepts {"is_read": true} to mark as read (v1 used POST /read/).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'support.edit'

    @extend_schema(
        summary='Detalle de mensaje de contacto (admin, v2)',
        tags=['admin-contact'],
        responses={200: ContactMessageAdminSerializer,
                   404: error_response('Mensaje no encontrado')},
    )
    def get(self, request, message_id):
        return AdminContactMessageDetailView().get(request, message_id=message_id)

    @extend_schema(
        summary='Marcar mensaje de contacto como leído (admin, v2)',
        tags=['admin-contact'],
        request=inline_serializer(
            name='ContactMessageMarkReadRequest',
            fields={'is_read': serializers.BooleanField()},
        ),
        responses={200: ContactMessageAdminSerializer,
                   400: error_response('INVALID_PAYLOAD'),
                   404: error_response('Mensaje no encontrado')},
    )
    def patch(self, request, message_id):
        if not request.data.get('is_read'):
            return Response(
                {'detail': 'is_read requerido y debe ser true.', 'codigo_error': 'INVALID_PAYLOAD'},
                status=400,
            )
        return AdminContactMessageMarkReadView().post(request, message_id=message_id)


class AdminContactMessageReplyV2View(APIView):
    """POST /api/v2/admin/contact/messages/<id>/replies/ — Tier A."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'support.edit'

    @extend_schema(
        summary='Responder mensaje de contacto por email (admin, v2)',
        tags=['admin-contact'],
        request=ContactMessageReplySerializer,
        responses={200: ContactMessageAdminSerializer,
                   400: error_response('BODY_REQUIRED'),
                   404: error_response('Mensaje no encontrado'),
                   409: error_response('MESSAGE_ALREADY_REPLIED')},
    )
    def post(self, request, message_id):
        return AdminContactMessageReplyView().post(request, message_id=message_id)
