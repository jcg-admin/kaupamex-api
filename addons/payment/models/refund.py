"""Modelo ``Refund`` — addon ``payment`` (reembolso de la transacción)."""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from addons.base.models import TimeStampedModel
from .payment import Payment


class Refund(TimeStampedModel):
    """
    Registro de un reembolso asociado a un pago. UC-PAY-07 (Sprint 17).
    El modelo existe en Sprint 15 para que Payment pueda relacionarse.
    Los endpoints de reembolso se crean en Sprint 17.
    """
    STATUS_PENDING   = 'PENDING'
    STATUS_APPROVED  = 'APPROVED'
    STATUS_FAILED    = 'FAILED'
    STATUSES = [
        (STATUS_PENDING,  'Pendiente'),
        (STATUS_APPROVED, 'Aprobado'),
        (STATUS_FAILED,   'Fallido'),
    ]

    payment           = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name='refunds',
    )
    amount            = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    reason            = models.TextField(blank=True, default='')
    gateway_refund_id = models.CharField(max_length=200, null=True, blank=True)
    status            = models.CharField(
        max_length=20, choices=STATUSES, default=STATUS_PENDING, db_index=True,
    )

    class Meta:
        db_table     = 'payments_refund'
        ordering     = ['-created_at']
        verbose_name = 'Reembolso'

    def __str__(self):
        # H-CICLO44-02: usar payment_id/order_id en lugar de traversar
        # self.payment.sale_order.name para evitar 2 queries FK en
        # listados del admin (N+1).
        return f'Reembolso {self.amount} — payment_id={self.payment_id}'
