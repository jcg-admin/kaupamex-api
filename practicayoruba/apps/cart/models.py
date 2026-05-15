"""
Models — apps.cart

Sprint 12 — UC-CART-01/02/03/05/06

Persistencia hibrida (ADR-005 adaptado para JWT):
- Visitante anonimo: Cart en BD vinculado a cart_token UUID.
  El cliente recibe el token en el primer POST y lo envia
  en header X-Cart-Token en requests subsiguientes.
- Comprador autenticado: Cart en BD vinculado a user.
Al hacer login el cliente llama POST /api/v1/cart/merge/
para fusionar el carrito anonimo con el del usuario.
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class Cart(models.Model):
    """
    Carrito de compras. UC-CART-01/02/03.
    Un usuario autenticado tiene como maximo un Cart activo.
    Un visitante anonimo tiene un Cart identificado por cart_token.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name='cart',
    )
    cart_token  = models.UUIDField(
        unique=True, null=True, blank=True, db_index=True,
        help_text='Token para visitantes anonimos. Enviado via X-Cart-Token.',
    )
    voucher     = models.ForeignKey(
        'voucher.Voucher', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='carts',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'cart_cart'
        verbose_name = 'Carrito'
        constraints  = [
            # Un usuario autenticado tiene solo un carrito activo
            models.UniqueConstraint(
                fields=['user'], condition=models.Q(user__isnull=False),
                name='unique_user_cart',
            ),
        ]

    def __str__(self):
        if self.user:
            return f'Cart de {self.user.username}'
        return f'Cart anonimo {self.cart_token}'

    def get_subtotal(self) -> Decimal:
        """Suma de unit_price * quantity de todos los items."""
        return sum(
            item.get_subtotal() for item in self.items.select_related('variant__product')
        ) or Decimal('0.00')

    def get_discount(self) -> Decimal:
        """Descuento del voucher aplicado, si existe. UC-CART-04 (FR-CART-04.02)."""
        if not self.voucher_id:
            return Decimal('0.00')
        return self.voucher.calculate_discount(self.get_subtotal())

    def get_free_shipping_threshold(self) -> Decimal | None:
        """Umbral de envio gratis desde SiteSettings."""
        from apps.settings_app.models import SiteSettings
        threshold = SiteSettings.get_current().free_shipping_threshold
        return threshold if threshold > 0 else None

    def get_totals(self) -> dict:
        """
        Calcula el desglose completo. FR-CART-02.02.
        shipping_cost: null en Sprint 12 (se selecciona en checkout).
        """
        from apps.settings_app.models import SiteSettings
        subtotal     = self.get_subtotal()
        discount     = self.get_discount()
        subtotal_net = subtotal - discount
        threshold    = self.get_free_shipping_threshold()
        iva_rate     = SiteSettings.get_current().iva_rate
        # IVA incluido en el precio
        tax          = (subtotal_net * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
        free_shipping_remaining = (
            max(Decimal('0.00'), threshold - subtotal_net)
            if threshold else None
        )
        return {
            'subtotal':                  str(subtotal),
            'discount':                  str(discount),
            'subtotal_net':              str(subtotal_net),
            'tax_included':              str(tax),
            'shipping_cost':             None,   # Sprint 18: metodo de envio seleccionado
            'total':                     str(subtotal_net),
            'free_shipping_threshold':   str(threshold) if threshold else None,
            'free_shipping_remaining':   str(free_shipping_remaining) if free_shipping_remaining else None,
            'free_shipping_applied':     bool(
                (threshold and subtotal_net >= threshold) or
                (self.voucher_id and self.voucher.voucher_type == 'FREE_SHIPPING')
            ),
            'item_count':                self.items.count(),
        }

    def merge(self, other_cart: 'Cart') -> None:
        """
        Fusiona other_cart en self. UC-CART-06 (FR-CART-06.02).
        Para cada item de other_cart:
          - Si la variante ya esta en self: suma cantidades.
          - Si no: mueve el CartItem a self.
        Elimina other_cart al terminar.
        """
        from django.db import transaction
        with transaction.atomic():
            for other_item in other_cart.items.select_related('variant__product').all():
                existing = self.items.filter(variant=other_item.variant).first()
                if existing:
                    existing.quantity += other_item.quantity
                    # Actualizar unit_price al precio actual
                    existing.unit_price = other_item.variant.effective_price()
                    existing.save(update_fields=['quantity', 'unit_price'])
                else:
                    other_item.cart = self
                    other_item.save(update_fields=['cart'])
            other_cart.delete()


class CartItem(models.Model):
    """
    Item dentro del carrito. UC-CART-01/02/03.
    variant es nullable: None para productos sin variantes.
    unit_price NO es snapshot — se actualiza al precio vigente en cada request.
    """
    cart       = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name='items',
    )
    variant    = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.CASCADE, related_name='cart_items',
    )
    product    = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='cart_items',
        help_text='Producto directo (para productos sin variantes).',
    )
    quantity   = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Precio actual del item. No es snapshot — se actualiza en cada GET.',
    )

    class Meta:
        db_table        = 'cart_cart_item'
        unique_together = [('cart', 'variant')]
        verbose_name    = 'Item de carrito'

    def __str__(self):
        label = self.variant.option.label if self.variant else self.product.name
        return f'{self.product.name} ({label}) ×{self.quantity}'

    def get_subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    def current_price(self) -> Decimal:
        """Precio efectivo actual de la variante o del producto."""
        if self.variant:
            return self.variant.effective_price()
        return self.product.price

    def is_available(self) -> bool:
        """Verifica stock actual."""
        if self.variant:
            return self.variant.is_available() and self.variant.stock >= self.quantity
        return self.product.stock >= self.quantity

    def available_stock(self) -> int:
        if self.variant:
            return self.variant.stock
        return self.product.stock


class SavedCart(models.Model):
    """
    Carrito guardado para despues. UC-CART-05.
    Un carrito guardado por usuario (OneToOne).
    Los items guardan el precio al momento del guardado.
    """
    user     = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='saved_cart',
    )
    saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'cart_saved_cart'
        verbose_name = 'Carrito guardado'

    def __str__(self):
        return f'Carrito guardado de {self.user.username}'


class SavedCartItem(models.Model):
    """Item dentro del carrito guardado."""
    saved_cart   = models.ForeignKey(
        SavedCart, on_delete=models.CASCADE, related_name='items',
    )
    product      = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
    )
    quantity     = models.PositiveIntegerField(default=1)
    price_at_save = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table        = 'cart_saved_cart_item'
        unique_together = [('saved_cart', 'product')]
        verbose_name    = 'Item guardado'

    def __str__(self):
        return f'{self.product.name} ×{self.quantity}'
