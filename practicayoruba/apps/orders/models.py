"""
Models — apps.orders
Sprint 14 — UC-ORD-01: Crear Orden desde Carrito (Checkout)

BR-005: OrderItem, OrderValue, OrderAddress son snapshots INMUTABLES.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import SoftDeleteModel, TimeStampedModel
from django.core.validators import MinValueValidator



def _generate_order_number() -> str:
    """PY-{8 chars UUID uppercase}. Único sin riesgo de colisión concurrente."""
    return f'PY-{str(uuid.uuid4())[:8].upper()}'


class Order(TimeStampedModel, SoftDeleteModel):
    """Orden de compra. Hereda SoftDeleteModel (DEC-DOC-007)."""
    STATUS_PENDING              = 'PENDING'
    STATUS_PROCESSING           = 'PROCESSING'
    STATUS_IN_PREPARATION       = 'IN_PREPARATION'
    STATUS_SHIPPED              = 'SHIPPED'
    STATUS_DELIVERED            = 'DELIVERED'
    STATUS_CANCELLED            = 'CANCELLED'
    STATUS_CANCELLED_BY_TIMEOUT = 'CANCELLED_TIMEOUT'
    STATUS_REFUNDED             = 'REFUNDED'
    STATUS_PAID                 = 'PAID'
    STATUSES = [
        (STATUS_PENDING,              'Pendiente de pago'),
        (STATUS_PROCESSING,           'Procesando pago'),
        (STATUS_PAID,                 'Pagado'),
        (STATUS_IN_PREPARATION,       'En preparación'),
        (STATUS_SHIPPED,              'Enviado'),
        (STATUS_DELIVERED,            'Entregado'),
        (STATUS_CANCELLED,            'Cancelado'),
        (STATUS_CANCELLED_BY_TIMEOUT, 'Cancelado por timeout'),
        (STATUS_REFUNDED,             'Reembolsado'),
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
    notes               = models.TextField(blank=True, default='')
    # UC-ORD-08 — cancelación admin (H-ADM-003)
    admin_cancelled_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='admin_cancelled_orders',
        help_text='Admin que canceló la orden. Null si la cancela el comprador.',
    )
    # UC-ORD-04 — campos de cancelación (H-ORD-001)
    cancellation_reason = models.TextField(
        blank=True, default='',
        help_text='Motivo de la cancelación (comprador o admin).'
    )
    cancelled_at        = models.DateTimeField(
        null=True, blank=True,
        help_text='Timestamp de la cancelación. Null si la orden no está cancelada.'
    )
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
    product         = models.ForeignKey(
        'catalogue.Product', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='order_items',
        help_text='Producto original. null si fue eliminado. No es snapshot.'
    )
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


class OrderStatusLog(TimeStampedModel):
    """
    Registro de auditoría de cambios de estado de órdenes.
    UC-ORD-07 (FR-ORD-07.02) — H-ADM-001.

    Cada transición de estado crea un registro inmutable con:
    - Estado anterior y nuevo estado
    - Administrador responsable (null si es el sistema)
    - Timestamp (created_at de TimeStampedModel)
    - Notas opcionales sobre el cambio
    """
    order           = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='status_logs',
    )
    previous_status = models.CharField(max_length=20)
    new_status      = models.CharField(max_length=20)
    changed_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='order_status_changes',
        help_text='Usuario que realizó el cambio. Null si fue el sistema.',
    )
    notes           = models.TextField(blank=True, default='')

    # DEC-003: override para db_index en tabla de historial — queries de
    # historial ordenadas por created_at son frecuentes en el admin.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table     = 'orders_status_log'
        ordering     = ['-created_at']
        verbose_name = 'Historial de estado de orden'

    def __str__(self):
        return (
            f'{self.order.order_number}: '
            f'{self.previous_status} → {self.new_status}'
        )


class CheckoutAttempt(models.Model):
    """
    Caché de respuestas de checkout para idempotencia. DEC-BC-03.
    UNIQUE(user, idempotency_key) previene doble orden con la misma clave.
    """
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='checkout_attempts',
    )
    idempotency_key = models.CharField(max_length=100)
    response_json   = models.TextField(default='')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'orders_checkout_attempt'
        unique_together = [('user', 'idempotency_key')]
        verbose_name    = 'Checkout attempt'

    def __str__(self):
        return f'{self.user_id}/{self.idempotency_key}'


class ShippingZone(models.Model):
    """
    Zona de envío cubierta. DEC-BC-18.
    zip_code_prefix es el inicio del código postal cubierto (1-5 dígitos).
    Ejemplo: "44" cubre todos los CP que empiezan con "44" (Guadalajara, JAL).
    """
    name            = models.CharField(max_length=100)
    zip_code_prefix = models.CharField(max_length=5, db_index=True)
    is_active       = models.BooleanField(default=True)

    class Meta:
        db_table = 'orders_shipping_zone'

    def __str__(self):
        return f'{self.name} ({self.zip_code_prefix})'
