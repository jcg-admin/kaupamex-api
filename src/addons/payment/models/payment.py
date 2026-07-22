"""Modelo ``Payment`` — addon ``payment`` (~ ``payment.transaction`` de Odoo).

Intento/transacción de pago de una orden. Movido desde ``payments`` a su hogar
fiel: el framework de pagos de Odoo (módulo ``payment``). La lógica específica
de MercadoPago vive aparte, en ``payment_mercado_pago``.
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from addons.base.models import TimeStampedModel


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
    # V3a orders→sale (DEC-FW-02): en Odoo el eje de pago vive en
    # payment.transaction anclado a sale.order — Payment (la transacción
    # strangler) gana la FK al canónico; V5 retira la FK legacy.
    sale_order        = models.ForeignKey(
        'sale.SaleOrder', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='payments',
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
