"""Modelo ``Payment`` — addon ``payment`` (~ ``payment.transaction`` de Odoo).

Intento/transacción de pago de una orden. Movido desde ``payments`` a su hogar
fiel: el framework de pagos de Odoo (módulo ``payment``). La lógica específica
de MercadoPago vive aparte, en ``payment_mercado_pago``.
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from addons.base.models import TimeStampedModel
from addons.bus.mixins import BusListenerMixin
from addons.bus.services import user_channel


class Payment(BusListenerMixin, TimeStampedModel):
    """
    Registro de un intento de pago para una orden. UC-PAY-01.
    Una orden puede tener múltiples Payment (reintentos).
    El Payment definitivo tiene status=APPROVED.

    preference_id: ID de preferencia MP / ID de orden PayPal.
    gateway_payment_id: ID del pago confirmado por el gateway.
    """
    GATEWAY_MERCADOPAGO = 'MERCADOPAGO'
    GATEWAY_PAYPAL      = 'PAYPAL'
    # O2C R8: conciliación manual del admin (UC-ORD-07). En Odoo el pago
    # registrado a mano es un payment.provider tipo 'custom' (transferencia,
    # efectivo); aquí el eje de pago lo registra con gateway MANUAL para que
    # la proyección canónica derive PAID sin pasar por una pasarela.
    GATEWAY_MANUAL      = 'MANUAL'
    GATEWAYS = [
        (GATEWAY_MERCADOPAGO, 'MercadoPago'),
        (GATEWAY_PAYPAL,      'PayPal'),
        (GATEWAY_MANUAL,      'Conciliación manual'),
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

    # E4-pre (H-API-26): anclaje invertido — la venta canónica manda
    # (NOT NULL, PROTECT). Desde E5 es el único ancla: la FK al espejo se
    # retiró con el addon ``orders``.
    #
    # H-API-97 — corrección del claim anterior: en la referencia
    # ``payment.transaction`` NO cuelga de ``sale.order`` por FK directa; su
    # ``reference`` es un ``Char`` de texto libre y el puente al documento de
    # negocio lo pone el addon ``sale``. Nuestro anclaje por FK es una
    # divergencia deliberada, no una copia.
    sale_order        = models.ForeignKey(
        'sale.SaleOrder', on_delete=models.PROTECT, related_name='payments',
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
        return f'{self.sale_order.name} — {self.gateway} — {self.status}'

    @property
    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED

    #: Estados que el comprador está esperando ver. ``PENDING`` no entra: es el
    #: estado en el que ya está mirando la pantalla, así que no es noticia.
    ESTADOS_QUE_AVISAN = (
        STATUS_APPROVED, STATUS_FAILED, STATUS_CANCELLED,
        STATUS_REFUNDED, STATUS_PARTIALLY_REFUNDED,
    )

    def bus_channel_key(self) -> str:
        return user_channel(self.sale_order.partner)

    def save(self, *args, **kwargs):
        # Sólo la transición emite. Sin esto, cada save del webhook (que toca
        # varios campos) reencolaría el mismo estado y la UI vería ruido.
        anterior = None
        if not self._state.adding:
            anterior = type(self).objects.filter(pk=self.pk).values_list(
                'status', flat=True,
            ).first()
        super().save(*args, **kwargs)

        if self.status == anterior or self.status not in self.ESTADOS_QUE_AVISAN:
            return
        # Carrito anónimo: sin comprador no hay canal privado al que avisar.
        if not self.sale_order.partner_id:
            return
        self._bus_send('pago.estado', {
            'payment_id': self.pk,
            'sale_order_id': self.sale_order_id,
            'status': self.status,
        })
