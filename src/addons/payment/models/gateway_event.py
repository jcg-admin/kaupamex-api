"""Modelo ``PaymentGatewayEvent`` — addon ``payment`` (auditoría del proveedor)."""
from django.db import models
from addons.base.models import TimeStampedModel
from .payment import Payment


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
        # H-CICLO44-02: usar payment_id en lugar de traversar
        # self.payment.sale_order.name para evitar 2 queries FK en
        # listados del admin (N+1).
        return f'{self.event_type} — payment_id={self.payment_id}'
