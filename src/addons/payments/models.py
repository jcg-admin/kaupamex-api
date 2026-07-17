"""
Models — addons.payments
Sprint 15 — UC-PAY-01, UC-PAY-01-EXT

Modelos documentados en modelo-payment.rst.
Todos heredan de TimeStampedModel (iniciativa herencia-modelos-django).

H-S15-001: PaymentGatewayEvent usa created_at (no received_at) — normalizado
a TimeStampedModel. La semántica es idéntica.
"""
import secrets
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from core.models import TimeStampedModel



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
        help_text='ID del pago confirmado por el gateway. Null hasta el webhook. '
                  'En Orders API guarda el PAY... anidado (transactions.payments[].id).',
    )
    mp_order_id       = models.CharField(
        max_length=200, null=True, blank=True, db_index=True,
        help_text='ID del recurso Order de MercadoPago (ORD...). Solo Orders API '
                  '(DEC-ORD-03); null para Payments-legacy y PayPal.',
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
        # H-CICLO44-02: usar payment_id/order_id en lugar de traversar
        # self.payment.order.order_number para evitar 2 queries FK en
        # listados del admin (N+1).
        return f'Reembolso {self.amount} — payment_id={self.payment_id}'


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
        # self.payment.order.order_number para evitar 2 queries FK en
        # listados del admin (N+1).
        return f'{self.event_type} — payment_id={self.payment_id}'


class WebhookEvent(models.Model):
    """
    Registro dedup para idempotencia de webhooks entrantes. DEC-BC-04.
    UNIQUE(gateway, event_id, transmission_id) previene doble procesamiento.
    INSERT falla con IntegrityError si el evento ya fue procesado.
    """
    gateway         = models.CharField(max_length=20)
    event_id        = models.CharField(max_length=100)
    transmission_id = models.CharField(max_length=100, blank=True, default='')
    raw_body        = models.TextField()
    processed_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'payments_webhook_event'
        constraints  = [
            models.UniqueConstraint(
                fields=['gateway', 'event_id', 'transmission_id'],
                name='unique_webhook_event',
            )
        ]
        verbose_name = 'Webhook event'

    def __str__(self):
        return f'{self.gateway}/{self.event_id}'


def _make_verification_token():
    return secrets.token_urlsafe(48)


class SavedCard(TimeStampedModel):
    """
    Tarjeta guardada por un usuario autenticado en MercadoPago Customer Cards.

    Flujo de verificación por email (seguridad interna):
    1. Usuario solicita guardar tarjeta → status=PENDING_VERIFICATION
    2. Se envía email con link que contiene verification_token
    3. Usuario hace clic → status=ACTIVE
    4. Solo tarjetas ACTIVE se muestran en el checkout

    mp_card_id es el ID de la tarjeta en el sistema de MP.
    mp_customer_id duplica el campo del User para consultas sin JOIN.
    """
    STATUS_PENDING  = 'pending_verification'
    STATUS_ACTIVE   = 'active'
    STATUS_DELETED  = 'deleted'
    STATUSES = [
        (STATUS_PENDING, 'Pendiente de verificación'),
        (STATUS_ACTIVE,  'Activa'),
        (STATUS_DELETED, 'Eliminada'),
    ]

    user               = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_cards',
    )
    mp_card_id         = models.CharField(max_length=100, db_index=True)
    mp_customer_id     = models.CharField(max_length=100, db_index=True)
    last_four_digits   = models.CharField(max_length=4)
    first_six_digits   = models.CharField(max_length=6, blank=True, default='')
    expiration_month   = models.PositiveSmallIntegerField()
    expiration_year    = models.PositiveSmallIntegerField()
    payment_method_id  = models.CharField(max_length=50, blank=True, default='')
    cardholder_name    = models.CharField(max_length=200, blank=True, default='')
    status             = models.CharField(
        max_length=30, choices=STATUSES, default=STATUS_PENDING, db_index=True,
    )
    verification_token = models.CharField(
        max_length=100, unique=True, default=_make_verification_token,
        help_text='Token de un solo uso enviado por email para activar la tarjeta.',
    )

    class Meta:
        db_table     = 'payments_saved_card'
        ordering     = ['-created_at']
        verbose_name = 'Tarjeta guardada'
        constraints  = [
            models.UniqueConstraint(
                fields=['user', 'mp_card_id'],
                name='unique_user_mp_card',
            )
        ]

    def __str__(self):
        return f'****{self.last_four_digits} ({self.payment_method_id}) — {self.status}'
