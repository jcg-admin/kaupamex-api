"""``SupportTicket`` — ticket de soporte post-venta (UC-SUPP-01..05).

Un archivo por modelo, espejo del layout de la referencia
(``odoo19e: helpdesk/models/``, mismo en ``odoo18e:``). Identificadores en
inglés según DEC-DOC-005.
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
