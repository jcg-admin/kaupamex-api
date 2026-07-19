"""``AdminCampaignCreateView`` — crear/enviar campaña de newsletter (UC-NEW-04).

Crea un ``mailing.mailing`` (hogar del ``NewsletterCampaign`` disuelto) y encola
el envío por destinatario vía ``dispatch_email`` (cola async EmailTask + cron).
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.company.models import CompanySetting
from addons.mail.models.email_executor import dispatch_email

from .. import services as mm
from ..serializers import CampaignCreateSerializer, CampaignResponseSerializer
from .base import NEWSLETTER_FROM_EMAIL_DEFAULT, _AdminOnly

_CAMPAIGN_DEDUP_WINDOW = timedelta(minutes=10)


class AdminCampaignCreateView(_AdminOnly, APIView):
    """POST /api/v2/admin/newsletter/campaigns/ — UC-NEW-04.

    H-CICLO78-01: guarda de idempotencia contra doble envio. Un segundo POST
    idéntico (mismo subject + body) dentro de la ventana de deduplicación
    retorna 409 CAMPAIGN_ALREADY_SENT. La comprobación va dentro de
    ``transaction.atomic()`` con ``select_for_update()`` para evitar la race
    condition en envíos concurrentes desde distintos procesos WSGI.
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

        audience_filter = vdata.get('audience_filter', mm.STATUS_CONFIRMED)
        subject = vdata['subject']
        body = vdata['body']

        with transaction.atomic():
            # H-CICLO78-01: duplicate guard — lock rows to prevent concurrent
            # double-send from multiple WSGI processes.
            cutoff = timezone.now() - _CAMPAIGN_DEDUP_WINDOW
            existing = mm.find_recent_mailing(subject, body, cutoff)
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

            recipients = mm.recipients_for(audience_filter)

            if not recipients:
                return Response(
                    {
                        'detail': (
                            'El segmento seleccionado no tiene '
                            'destinatarios activos.'
                        ),
                        'codigo_error': 'NO_RECIPIENTS',
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            mailing = mm.create_mailing(
                subject=subject,
                body_html=body,
                user=request.user,
                recipients_count=len(recipients),
            )

        # UC-NEW-04: el envío real se encola de forma ASÍNCRONA vía
        # dispatch_email (thread pool + EmailTask queue / cron). El request NO
        # bloquea en un loop síncrono de SMTP; un email por destinatario para
        # reintento por-destino.
        for recipient_email in recipients:
            dispatch_email(
                subject=mailing.subject,
                message=body,
                from_email=CompanySetting.get_setting(
                    'newsletter.from_email', NEWSLETTER_FROM_EMAIL_DEFAULT,
                ),
                recipient_list=[recipient_email],
            )

        return Response(
            {
                'id': mailing.pk,
                'subject': mailing.subject,
                'audience_filter': audience_filter,
                'recipients_count': len(recipients),
                'sent_at': mailing.sent_date,
            },
            status=status.HTTP_201_CREATED,
        )
