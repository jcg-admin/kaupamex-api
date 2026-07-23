"""Modelo ``Chargeback`` — addon ``payment`` (contracargo del emisor)."""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from addons.base.models import TimeStampedModel
from .payment import Payment


class Chargeback(TimeStampedModel):
    """
    Contracargo iniciado por el tarjetahabiente vía banco emisor. T-17.
    MP envía topic=chargebacks con el chargeback_id; se consulta el detalle
    con sdk.chargeback().get(id) y se persiste aquí.
    """
    STATUS_PENDING   = 'pending'
    STATUS_LOST      = 'lost'
    STATUS_WON       = 'won'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CLOSED    = 'closed'
    STATUSES = [
        (STATUS_PENDING,   'Pendiente'),
        (STATUS_LOST,      'Perdido'),
        (STATUS_WON,       'Ganado'),
        (STATUS_CANCELLED, 'Cancelado'),
        (STATUS_CLOSED,    'Cerrado'),
    ]

    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chargebacks',
    )
    gateway_chargeback_id = models.CharField(
        max_length=200, unique=True, db_index=True,
    )
    gateway_payment_id = models.CharField(max_length=200, db_index=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    status = models.CharField(
        max_length=20, choices=STATUSES, default=STATUS_PENDING, db_index=True,
    )
    reason_code = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True, default='')

    class Meta:
        db_table     = 'payments_chargeback'
        ordering     = ['-created_at']
        verbose_name = 'Contracargo'

    def __str__(self):
        return f'Chargeback {self.gateway_chargeback_id} — {self.status}'
