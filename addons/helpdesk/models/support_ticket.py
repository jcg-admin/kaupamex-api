"""``SupportTicket`` — ticket de soporte post-venta (UC-SUPP-01..05).

Un archivo por modelo, espejo del layout de la referencia
(``odoo19e: helpdesk/models/``, mismo en ``odoo18e:``). Identificadores en
inglés según DEC-DOC-005.
"""
import logging
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from addons.base.models import SoftDeleteModel, TimeStampedModel
from addons.mail.models import MailActivityMixin, MailThread

logger = logging.getLogger(__name__)

# Cierre por inactividad (UC-NOT-08). Valores del comando que hospedaba la
# lógica; el cron los usa por defecto porque el runner invoca sin argumentos.
AUTO_CLOSE_DAYS = 7
_AUTO_CLOSE_BATCH = 100
AUTO_CLOSE_BODY = (
    f'Este ticket fue cerrado automaticamente por inactividad '
    f'(sin respuesta del usuario durante {AUTO_CLOSE_DAYS} dias).'
)


class SupportTicket(MailThread, MailActivityMixin, TimeStampedModel, SoftDeleteModel):
    """Ticket de soporte. UC-SUPP-01.

    Hereda ``MailActivityMixin`` con la misma composición que la referencia da
    a su ticket: ``helpdesk.ticket`` declara ``'mail.activity.mixin'`` entre sus
    mixins (``odoo19e: helpdesk/models/helpdesk_ticket.py:36``). Ese addon es
    **OEEL-1**, así que se adopta la *forma* —qué mixins componen un ticket— y
    no su código, que se reimplementa nativo (DEC-KX-03).

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

    # ------------------------------------------------------------------
    # Cierre por inactividad — el método que el cron invoca (UC-NOT-08)
    # ------------------------------------------------------------------

    @classmethod
    def auto_close_stale(cls, dias=AUTO_CLOSE_DAYS, batch_size=_AUTO_CLOSE_BATCH):
        """Cierra tickets ``AWAITING_USER`` sin actividad. ``(cerrados, fallidos)``.

        Vivía en el ``handle()`` de un management command, así que ``ir.cron``
        —que resuelve ``<model>.<method>()``— no tenía a qué apuntar.

        Cada ticket va en su **propia** transacción y su fallo se registra sin
        abortar el lote: un ticket con datos corruptos no debe impedir que se
        cierren los demás. Es la misma tolerancia que tenía el comando.
        """
        umbral = timezone.now() - timedelta(days=dias)
        ticket_ids = list(
            cls.objects.filter(
                status=cls.Status.AWAITING_USER, updated_at__lte=umbral,
            )
            .order_by('updated_at')
            .values_list('pk', flat=True)[:batch_size]
        )

        cerrados = fallidos = 0
        for pk in ticket_ids:
            try:
                cls._close_stale_one(pk)
                cerrados += 1
            except Exception as exc:
                logger.error('auto_close_stale: pk=%s error=%s', pk, exc)
                fallidos += 1
        return cerrados, fallidos

    @classmethod
    def _close_stale_one(cls, pk):
        """Cierra un ticket y deja la respuesta de aviso, en una transacción."""
        # apps.get_model, no un import: support_ticket_reply importa
        # SupportTicket (support_ticket_reply.py:6), así que el import al top
        # sería un ciclo REAL — verificado. Excepción #3 de no-lazy-imports:
        # el ciclo se rompe con una llamada, no con un import diferido.
        SupportTicketReply = apps.get_model('helpdesk', 'SupportTicketReply')

        with transaction.atomic():
            ticket = (
                cls.objects
                .select_for_update(skip_locked=True)
                .filter(pk=pk, status=cls.Status.AWAITING_USER)
                .first()
            )
            if ticket is None:
                return

            # _closed_by_staff=True → el signal notifica como staff.
            ticket._closed_by_staff = True
            ticket.status = cls.Status.CLOSED
            ticket.save(update_fields=['status', 'updated_at'])

            SupportTicketReply.objects.create(
                ticket=ticket, author=None,
                body=AUTO_CLOSE_BODY, is_internal_note=False,
            )
