"""
Models — apps.payments
Sprint 15 — UC-PAY-01, UC-PAY-01-EXT

Modelos documentados en modelo-payment.rst.
Todos heredan de TimeStampedModel (iniciativa herencia-modelos-django).

H-S15-001: PaymentGatewayEvent usa created_at (no received_at) — normalizado
a TimeStampedModel. La semántica es idéntica.
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

from apps.core.models import TimeStampedModel


class Payment(TimeStampedModel):
    """
    Registro de un intento de pago para una orden. UC-PAY-01.
    Una orden puede tener múltiples Payment (reintentos).
    El Payment definitivo tiene status=APPROVED.

    preference_id: ID de preferencia MP / ID de orden PayPal.
    gateway_payment_id: ID del pago confirmado por el gateway.
    """
    GATEWAY_MERCADOPAGO = 'MERCADOPAGO'
    GATEWAY_PAYPAL      = 'PAYPAL'
    GATEWAYS = [
        (GATEWAY_MERCADOPAGO, 'MercadoPago'),
        (GATEWAY_PAYPAL,      'PayPal'),
    ]

    STATUS_PENDING             = 'PENDING'
    STATUS_APPROVED            = 'APPROVED'
    STATUS_FAILED              = 'FAILED'
    STATUS_REFUNDED            = 'REFUNDED'
    STATUS_PARTIALLY_REFUNDED  = 'PARTIALLY_REFUNDED'
    STATUS_CANCELLED           = 'CANCELLED'
    STATUSES = [
        (STATUS_PENDING,            'Pendiente'),
        (STATUS_APPROVED,           'Aprobado'),
        (STATUS_FAILED,             'Fallido'),
        (STATUS_REFUNDED,           'Reembolsado'),
        (STATUS_PARTIALLY_REFUNDED, 'Reembolso parcial'),
        (STATUS_CANCELLED,          'Cancelado'),
    ]

    order             = models.ForeignKey(
        'orders.Order', on_delete=models.PROTECT, related_name='payments',
    )
    gateway           = models.CharField(max_length=20, choices=GATEWAYS, db_index=True)
    gateway_payment_id = models.CharField(
        max_length=200, null=True, blank=True, unique=True,
        help_text='ID del pago confirmado por el gateway. Null hasta el webhook.',
    )
    preference_id     = models.CharField(
        max_length=200, null=True, blank=True,
        help_text='ID de preferencia MP o ID de orden PayPal.',
    )
    status            = models.CharField(
        max_length=30, choices=STATUSES,
        default=STATUS_PENDING, db_index=True,
    )
    amount            = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Importe cobrado. Coincide con OrderValue.total al momento del pago.',
    )
    installments      = models.PositiveIntegerField(
        default=1,
        help_text='Número de cuotas. 1 = pago de contado.',
    )

    class Meta:
        db_table     = 'payments_payment'
        ordering     = ['-created_at']
        verbose_name = 'Pago'

    def __str__(self):
        return f'{self.order.order_number} — {self.gateway} — {self.status}'

    @property
    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED


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
        return f'Reembolso {self.amount} — {self.payment.order.order_number}'


class PaymentGatewayEvent(TimeStampedModel):
    """
    Registro de auditoría de eventos del gateway. UC-PAY-03/04 (Sprint 16).
    Acumula todos los eventos — nunca sobreescribe datos previos.

    H-S15-001: el modelo documentado usaba received_at. Se normaliza a
    created_at (TimeStampedModel). Semántica idéntica.
    """
    EVENT_WEBHOOK_RECEIVED = 'WEBHOOK_RECEIVED'
    EVENT_PREFERENCE_CREATED = 'PREFERENCE_CREATED'
    EVENT_PAYMENT_APPROVED = 'PAYMENT_APPROVED'
    EVENT_PAYMENT_FAILED   = 'PAYMENT_FAILED'
    EVENT_REFUND_CREATED   = 'REFUND_CREATED'
    EVENT_TYPES = [
        (EVENT_WEBHOOK_RECEIVED,   'Webhook recibido'),
        (EVENT_PREFERENCE_CREATED, 'Preferencia creada'),
        (EVENT_PAYMENT_APPROVED,   'Pago aprobado'),
        (EVENT_PAYMENT_FAILED,     'Pago fallido'),
        (EVENT_REFUND_CREATED,     'Reembolso creado'),
    ]

    payment    = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name='gateway_events',
    )
    event_type = models.CharField(max_length=40, choices=EVENT_TYPES, db_index=True)
    raw_body   = models.TextField(
        help_text='Respuesta completa del gateway almacenada como texto.',
    )

    class Meta:
        db_table     = 'payments_gateway_event'
        ordering     = ['-created_at']
        verbose_name = 'Evento del gateway'

    def __str__(self):
        return f'{self.event_type} — {self.payment.order.order_number}'
