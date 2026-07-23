"""
auto_close_support_tickets — management command (UC-NOT-08).

Cierra automaticamente tickets en estado AWAITING_USER que no han
tenido actividad por mas de AUTO_CLOSE_DAYS dias. El cierre dispara
el signal post_save de SupportTicket que envia UC-NOT-08 via
addons.mail.models.notification_signals.

Ejecutar via cron (sin Celery — cnst-arquitectura T6):
    0 * * * * cd /path/to/api && python manage.py auto_close_support_tickets

El campo updated_at de SupportTicket actua como proxy de ultima actividad:
el status transiciona a AWAITING_USER cuando staff responde, actualizando
updated_at. Si el comprador no responde, updated_at no cambia.
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from addons.helpdesk.models import SupportTicket, SupportTicketReply

logger = logging.getLogger(__name__)

AUTO_CLOSE_DAYS = 7
_BATCH_SIZE = 100
AUTO_CLOSE_BODY = (
    f'Este ticket fue cerrado automaticamente por inactividad '
    f'(sin respuesta del usuario durante {AUTO_CLOSE_DAYS} dias).'
)


class Command(BaseCommand):
    help = (
        f'Cierra tickets AWAITING_USER sin actividad '
        f'por {AUTO_CLOSE_DAYS} dias y notifica al usuario (UC-NOT-08).'
    )

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(days=AUTO_CLOSE_DAYS)
        ticket_ids = list(
            SupportTicket.objects.filter(
                status=SupportTicket.Status.AWAITING_USER,
                updated_at__lte=threshold,
            )
            .order_by('updated_at')
            .values_list('pk', flat=True)[:_BATCH_SIZE]
        )

        closed = failed = 0
        for pk in ticket_ids:
            try:
                self._close_ticket(pk)
                closed += 1
            except Exception as exc:
                logger.error(
                    'auto_close_support_tickets: pk=%s error=%s', pk, exc
                )
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'auto_close_support_tickets: closed={closed} failed={failed}'
            )
        )

    def _close_ticket(self, pk):
        with transaction.atomic():
            ticket = (
                SupportTicket.objects
                .select_for_update(skip_locked=True)
                .filter(pk=pk, status=SupportTicket.Status.AWAITING_USER)
                .first()
            )
            if ticket is None:
                return

            # _closed_by_staff=True → signal envia notificacion como staff.
            ticket._closed_by_staff = True
            ticket.status = SupportTicket.Status.CLOSED
            ticket.save(update_fields=['status', 'updated_at'])

            SupportTicketReply.objects.create(
                ticket=ticket,
                author=None,
                body=AUTO_CLOSE_BODY,
                is_internal_note=False,
            )
