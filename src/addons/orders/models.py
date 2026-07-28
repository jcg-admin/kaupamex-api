"""
Models — addons.orders
Sprint 14 — UC-ORD-01: Crear Orden desde Carrito (Checkout)

BR-005: OrderItem, OrderValue, OrderAddress son snapshots INMUTABLES.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from addons.base.models import SiteSettings, SoftDeleteModel, TimeStampedModel
from addons.mail.models import MailThread
from django.core.validators import MinValueValidator



def _generate_order_number() -> str:
    """PY-{8 chars UUID uppercase}. Único sin riesgo de colisión concurrente."""
    return f'PY-{str(uuid.uuid4())[:8].upper()}'


class Order(MailThread, TimeStampedModel, SoftDeleteModel):
    """Orden de compra. Hereda SoftDeleteModel (DEC-DOC-007)."""
    # S1 unificación cart→order→sale: el carrito de Odoo es un sale.order
    # en state='draft' — no una tabla aparte. DRAFT precede a PENDING; el
    # checkout es la transición DRAFT→PENDING (analisis-unificar-cart-order-sale).
    # E2a: el vocabulario de estado (``STATUS_*`` + ``STATUSES``) se movió a
    # ``orders.status_projection`` — el módulo que *produce* el estado. Aquí
    # era un acoplamiento invertido: 39 referencias importaban este modelo
    # espejo sólo para leer una constante, y la propia proyección tenía que
    # importarlo para nombrar su salida. Los valores no cambiaron.

    order_number    = models.CharField(max_length=20, unique=True, db_index=True)
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='orders',
    )
    guest_email     = models.EmailField(null=True, blank=True,
                          help_text='Email del comprador invitado (BR-011).')
    # O2C V5d (ADR-024): la columna espejo ``status`` fue RETIRADA. El estado se
    # deriva de los tres ejes canónicos vía ``status_projection.order_status``
    # (comercial ``sale.SaleOrder.state`` · pago ``Payment`` · fulfillment
    # ``ShipmentGuide``). Las constantes ``STATUS_*`` / ``STATUSES`` sobreviven
    # como **vocabulario** del contrato público (``?status=``, labels del
    # serializer, ``OrderStatusLog``), no como campo de esta tabla.
    #
    # S1 unificación cart→order→sale: token del carrito anónimo (paridad con
    # cart.Cart.cart_token). Solo los drafts anónimos lo llevan; la unicidad
    # UNIQUE admite múltiples NULL en SQL.
    cart_token      = models.UUIDField(
        unique=True, null=True, blank=True, db_index=True,
        help_text='Carrito anónimo — draft sin user (S1, analisis-unificar-cart-order-sale).')
    # V3a orders→sale (DEC-FW-02): el espejo legacy conoce su canónico.
    # O2C V5d: pasa a **obligatorio** (``null=False``) — sin canónica no hay
    # estado que derivar, y ``PROTECT`` impide que borrar la ``SaleOrder``
    # reintroduzca el ``NULL`` que el retiro de la columna espejo elimina
    # (``SET_NULL`` era la puerta trasera del fallback; ver H-API-19).
    sale_order      = models.OneToOneField(
        'sale.SaleOrder',
        on_delete=models.PROTECT, related_name='legacy_order',
        help_text='SaleOrder canónica de la que este Order es espejo (V3a).')
    shipping_method = models.ForeignKey(
        'delivery.ShippingMethod', null=True, blank=True,
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



    # S2c unificación cart→order→sale: desglose por línea con la MISMA
    # matemática de cart.CartItem.price_* (adaptación de Odoo
    # ``sale.order.line._compute_amount``: precios IVA-incluido MX, IVA
    # extraído y cuantizado por línea). OrderItem es la línea strangler de
    # ``sale.order.line`` mientras dura el cut-over.
    def price_total(self):
        """Total de la línea con IVA incluido."""
        return (self.unit_price * self.quantity).quantize(Decimal('0.01'))

    def price_tax(self):
        """IVA contenido en el total de la línea (extraído, tasa vigente)."""
        rate = SiteSettings.get_current().iva_rate
        return (self.price_total() * rate / (1 + rate)).quantize(Decimal('0.01'))

    def price_subtotal(self):
        """Subtotal de la línea sin IVA (total − IVA)."""
        return self.price_total() - self.price_tax()

    def current_price(self):
        """Precio vigente del catálogo (variant.effective_price o product.price)."""
        if self.variant:
            return self.variant.effective_price()
        return self.product.price if self.product else self.unit_price

    def is_available(self) -> bool:
        """Paridad con CartItem.is_available (guardias H-CICLO42-01)."""
        if self.product is None:
            return False
        if not (self.product.is_active and self.product.is_published):
            return False
        if self.variant:
            return self.variant.is_available() and self.variant.stock >= self.quantity
        return self.product.stock >= self.quantity

    def available_stock(self) -> int:
        if self.variant:
            return self.variant.stock
        return self.product.stock if self.product else 0

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
    # V1 orders→sale (DEC-FW-02): la FK legacy pasa a nullable — FK dual
    # transitoria; V2 conmuta el flujo vivo a sale.SaleOrder y V5 la retira.
    order          = models.OneToOneField(Order, null=True, blank=True,
                         on_delete=models.CASCADE, related_name='address')
    sale_order     = models.OneToOneField(
        'sale.SaleOrder', null=True, blank=True,
        on_delete=models.CASCADE, related_name='delivery_address',
    )
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
    # V1 orders→sale (DEC-FW-02): FK legacy nullable (dual transitoria).
    order           = models.ForeignKey(
        Order, null=True, blank=True,
        on_delete=models.CASCADE, related_name='status_logs',
    )
    sale_order      = models.ForeignKey(
        'sale.SaleOrder', null=True, blank=True,
        on_delete=models.CASCADE, related_name='status_logs',
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
        ref = self.order.order_number if self.order_id else (
            self.sale_order_id and str(self.sale_order) or 's/ref')
        return f'{ref}: {self.previous_status} → {self.new_status}'


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
        db_table     = 'orders_checkout_attempt'
        constraints  = [
            models.UniqueConstraint(
                fields=['user', 'idempotency_key'],
                name='unique_checkout_attempt',
            )
        ]
        verbose_name = 'Checkout attempt'

    def __str__(self):
        return f'{self.user_id}/{self.idempotency_key}'
