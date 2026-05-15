"""
Models — apps.orders
Sprint 14 — UC-ORD-01: Crear Orden desde Carrito (Checkout)

BR-005: OrderItem, OrderValue, OrderAddress son snapshots INMUTABLES.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from django.core.validators import MinValueValidator


def _generate_order_number() -> str:
    """PY-{8 chars UUID uppercase}. Único sin riesgo de colisión concurrente."""
    return f'PY-{str(uuid.uuid4())[:8].upper()}'


class Order(TimeStampedModel):
    STATUS_PENDING        = 'PENDING'
    STATUS_PROCESSING     = 'PROCESSING'
    STATUS_IN_PREPARATION = 'IN_PREPARATION'
    STATUS_SHIPPED        = 'SHIPPED'
    STATUS_DELIVERED      = 'DELIVERED'
    STATUS_CANCELLED      = 'CANCELLED'
    STATUS_REFUNDED       = 'REFUNDED'
    STATUSES = [
        (STATUS_PENDING,        'Pendiente de pago'),
        (STATUS_PROCESSING,     'Procesando pago'),
        (STATUS_IN_PREPARATION, 'En preparación'),
        (STATUS_SHIPPED,        'Enviado'),
        (STATUS_DELIVERED,      'Entregado'),
        (STATUS_CANCELLED,      'Cancelado'),
        (STATUS_REFUNDED,       'Reembolsado'),
    ]

    order_number    = models.CharField(max_length=20, unique=True, db_index=True)
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='orders',
    )
    guest_email     = models.EmailField(null=True, blank=True,
                          help_text='Email del comprador invitado (BR-011).')
    status          = models.CharField(max_length=20, choices=STATUSES,
                          default=STATUS_PENDING, db_index=True)
    shipping_method = models.ForeignKey(
        'settings_app.ShippingMethod', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='orders',
    )
    voucher_code    = models.CharField(max_length=50, blank=True, default='',
                          help_text='Código del voucher al momento del checkout.')
    voucher_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'))
    notes           = models.TextField(blank=True, default='')
    # DEC-003: override para mantener db_index en tabla de alto volumen
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # updated_at viene de TimeStampedModel

    class Meta:
        db_table = 'orders_order'
        ordering = ['-created_at']
        verbose_name = 'Orden'

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = _generate_order_number()
        super().save(*args, **kwargs)


class OrderItem(TimeStampedModel):
    """
    Snapshot inmutable de un item de la orden. BR-005.
    variant puede ser null si la variante fue eliminada del catálogo,
    pero product_name, sku y unit_price conservan el valor al checkout.
    """
    order         = models.ForeignKey(Order, on_delete=models.CASCADE,
                        related_name='items')
    variant       = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='order_items',
    )
    product_name  = models.CharField(max_length=200)
    variant_label = models.CharField(max_length=100, blank=True, default='')
    sku           = models.CharField(max_length=70)
    unit_price    = models.DecimalField(max_digits=10, decimal_places=2)
    quantity      = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    subtotal      = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'orders_order_item'
        verbose_name = 'Item de orden'

    def __str__(self):
        return f'{self.order.order_number} — {self.product_name}'


class OrderValue(TimeStampedModel):
    """Snapshot financiero de la orden. BR-005. OneToOne con Order."""
    order         = models.OneToOneField(Order, on_delete=models.CASCADE,
                        related_name='value')
    subtotal      = models.DecimalField(max_digits=10, decimal_places=2)
    tax           = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2,
                        default=Decimal('0.00'))
    discount      = models.DecimalField(max_digits=10, decimal_places=2,
                        default=Decimal('0.00'))
    total         = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'orders_order_value'


class OrderAddress(TimeStampedModel):
    """Snapshot de la dirección de envío al momento del checkout. BR-005."""
    order          = models.OneToOneField(Order, on_delete=models.CASCADE,
                         related_name='address')
    recipient_name = models.CharField(max_length=200)
    street         = models.CharField(max_length=255)
    city           = models.CharField(max_length=100)
    state          = models.CharField(max_length=100)
    zip_code       = models.CharField(max_length=10)
    country        = models.CharField(max_length=2, default='MX')
    phone          = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table = 'orders_order_address'
