"""``SupportTicketReply`` — mensaje del hilo de un ticket (UC-SUPP-03)."""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel
from addons.helpdesk.models.support_ticket import SupportTicket


class SupportTicketReply(TimeStampedModel):
    """Mensaje del hilo de conversacion de un ticket. UC-SUPP-03."""

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='replies',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='support_ticket_replies',
    )
    body = models.TextField()
    is_internal_note = models.BooleanField(default=False)

    class Meta:
        db_table = 'support_ticket_reply'
        ordering = ['created_at']
        verbose_name = 'Respuesta de ticket'
        verbose_name_plural = 'Respuestas de ticket'

    def __str__(self):
        return f'Reply #{self.pk} on ticket #{self.ticket_id}'
