"""
Models — addons.support (UC-SUPP-01..05).

Identificadores en ingles segun DEC-DOC-005.

SupportTicket modela un ticket de soporte post-venta abierto por un comprador.
SupportTicketReply modela cada mensaje del hilo de conversacion.
"""
from django.conf import settings
from django.db import models
from addons.base.models import SoftDeleteModel, TimeStampedModel
from addons.mail.models import MailThread



class SupportTicket(MailThread, TimeStampedModel, SoftDeleteModel):
    """Ticket de soporte. UC-SUPP-01.

    Hereda ``MailThread`` (addon ``mail``, ``mail.thread`` de Odoo): dota al
    ticket de chatter/seguidores (``message_post``/``message_subscribe``) sin
    agregar columnas — los mensajes viven en ``mail_message`` (polimorfico).

    Hereda de SoftDeleteModel (DEC-DOC-007): el historial de soporte
    se conserva incluso despues de una operacion DELETE del admin —
    es referenciado desde ``SupportTicketReply`` via CASCADE y se
    consulta en auditorias post-venta.
    """

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Abierto'
        IN_PROGRESS = 'IN_PROGRESS', 'En progreso'
        AWAITING_USER = 'AWAITING_USER', 'Esperando al usuario'
        RESOLVED = 'RESOLVED', 'Resuelto'
        CLOSED = 'CLOSED', 'Cerrado'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Baja'
        NORMAL = 'NORMAL', 'Normal'
        HIGH = 'HIGH', 'Alta'

    class Category(models.TextChoices):
        GENERAL = 'GENERAL', 'General'
        ORDER = 'ORDER', 'Orden'
        DAMAGED = 'DAMAGED', 'Producto dañado'
        URGENT = 'URGENT', 'Urgente'
        FRAUD = 'FRAUD', 'Fraude'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_tickets',
    )
    subject = models.CharField(max_length=150)
    body = models.TextField()
    category = models.CharField(
        max_length=16, choices=Category.choices, default=Category.GENERAL,
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN,
    )
    priority = models.CharField(
        max_length=8, choices=Priority.choices, default=Priority.NORMAL,
    )
    order_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'support_ticket'
        ordering = ['-created_at']
        verbose_name = 'Ticket de soporte'
        verbose_name_plural = 'Tickets de soporte'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'priority']),
        ]

    def __str__(self):
        return f'#{self.pk} {self.subject} ({self.status})'


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
