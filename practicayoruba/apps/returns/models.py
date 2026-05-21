"""
Models — apps.returns (UC-RET-01..06).

Identificadores en ingles segun DEC-DOC-005.

ReturnRequest: solicitud de devolucion creada por un comprador (UC-RET-01).
ReturnItem: items concretos incluidos en la devolucion (Alt. C de UC-RET-01).
ReturnHistoryEntry: pista de auditoria (UC-RET-04 expone el historial).
"""
from django.conf import settings
from django.db import models
from apps.core.models import SoftDeleteModel, TimeStampedModel



class ReturnRequest(TimeStampedModel, SoftDeleteModel):
    """Solicitud de devolucion. UC-RET-01..06.

    Hereda de SoftDeleteModel (DEC-DOC-007): un DELETE conserva la fila
    junto a sus ``ReturnItem`` y ``ReturnHistoryEntry`` (referenciados
    via CASCADE). El borrado fisico romperia el historial financiero y
    el rastro de auditoria que UC-RET-04 expone.
    """

    class Status(models.TextChoices):
        PENDING_REVIEW = 'PENDING_REVIEW', 'Pendiente de revision'
        INFO_REQUESTED = 'INFO_REQUESTED', 'Pendiente de informacion'
        APPROVED = 'APPROVED', 'Aprobada'
        REJECTED = 'REJECTED', 'Rechazada'
        RECEIVED = 'RECEIVED', 'Recibida'
        REFUNDED = 'REFUNDED', 'Reembolsada'

    class Reason(models.TextChoices):
        DAMAGED_PRODUCT = 'DAMAGED_PRODUCT', 'Producto danado'
        NOT_AS_DESCRIBED = 'NOT_AS_DESCRIBED', 'No coincide con la descripcion'
        CHANGED_MIND = 'CHANGED_MIND', 'Cambio de opinion'
        OTHER = 'OTHER', 'Otro'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='return_requests',
    )
    # Desacoplado de apps.orders (mismo patron que SupportTicket.order_id).
    order_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=24, choices=Reason.choices)
    description = models.TextField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING_REVIEW,
    )
    refund_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    refund_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'return_request'
        ordering = ['-created_at']
        verbose_name = 'Solicitud de devolucion'
        verbose_name_plural = 'Solicitudes de devolucion'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'ReturnRequest#{self.pk} order={self.order_id} ({self.status})'


class ReturnItem(TimeStampedModel):
    """Item especifico incluido en la solicitud (UC-RET-01 Alt C)."""

    class Condition(models.TextChoices):
        GOOD_CONDITION = 'GOOD_CONDITION', 'Buenas condiciones'
        DAMAGED = 'DAMAGED', 'Danado'
        INCOMPLETE = 'INCOMPLETE', 'Incompleto'

    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product_id = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField(default=1)
    product_condition = models.CharField(
        max_length=16, choices=Condition.choices, blank=True, default='',
    )

    class Meta:
        db_table = 'return_item'
        ordering = ['id']
        verbose_name = 'Item de devolucion'
        verbose_name_plural = 'Items de devolucion'

    def __str__(self):
        return f'ReturnItem#{self.pk} product={self.product_id}'


class ReturnHistoryEntry(TimeStampedModel):
    """Entrada del historial de cambios de estado (UC-RET-04 detail)."""

    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name='history_entries',
    )
    status_to = models.CharField(max_length=16, choices=ReturnRequest.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='return_history_entries',
    )
    justification = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'return_history_entry'
        ordering = ['created_at']
        verbose_name = 'Entrada de historial de devolucion'
        verbose_name_plural = 'Entradas de historial de devoluciones'

    def __str__(self):
        return (
            f'History#{self.pk} return={self.return_request_id} '
            f'-> {self.status_to}'
        )
