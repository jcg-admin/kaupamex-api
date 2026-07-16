"""
Models — apps.modules.cart

Sprint 12 — UC-CART-01/02/03/05/06
Refactorizado en sprint de infraestructura: herencia-modelos-django
  Cart        → TimeStampedModel (refactor puro, sin migración)
  CartItem    → TimeStampedModel (migración 0003: ADD created_at + updated_at)
  SavedCart   → TimeStampedModel (migración 0003: RENAME saved_at→updated_at + ADD created_at)
  SavedCartItem → TimeStampedModel (migración 0003: ADD created_at + updated_at)
"""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.core.validators import MinValueValidator
from apps.core.models import TimeStampedModel
from apps.modules.settings_app.models import SiteSettings



class Cart(TimeStampedModel):
    """
    Carrito de compras. UC-CART-01/02/03.
    Persistencia híbrida (ADR-005 adaptado para JWT).
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name='cart',
    )
    cart_token = models.UUIDField(
        unique=True, null=True, blank=True, db_index=True,
    )
    voucher    = models.ForeignKey(
        'voucher.Voucher', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='carts',
    )

    class Meta:
        db_table     = 'cart_cart'
        verbose_name = 'Carrito'
        # Cart.user es OneToOneField -> ya crea UNIQUE a nivel de BD.
        # SQL standard permite multiples NULLs en columnas UNIQUE
        # (NULL != NULL), asi que "un user max un cart, multiples
        # carritos anonimos" ya esta cubierto sin constraint adicional.
        # La UniqueConstraint(fields=['user'], condition=Q(...)) era
        # redundante y solo generaba el warning W036 en MariaDB.

    def __str__(self):
        if self.user:
            return f'Cart de {self.user.email}'
        return f'Cart anónimo {self.cart_token}'

    def get_subtotal(self) -> Decimal:
        return sum(
            item.get_subtotal() for item in self.items.select_related('variant__product')
        ) or Decimal('0.00')

    def get_discount(self) -> Decimal:
        if not self.voucher_id:
            return Decimal('0.00')
        return self.voucher.calculate_discount(self.get_subtotal())

    def get_free_shipping_threshold(self) -> Decimal | None:
        threshold = SiteSettings.get_current().free_shipping_threshold
        return threshold if threshold > 0 else None

    def get_totals(self) -> dict:
        subtotal     = self.get_subtotal()
        discount     = self.get_discount()
        subtotal_net = subtotal - discount
        threshold    = self.get_free_shipping_threshold()
        iva_rate     = SiteSettings.get_current().iva_rate
        tax          = (subtotal_net * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
        free_remaining = (
            max(Decimal('0.00'), threshold - subtotal_net) if threshold else None
        )
        return {
            'subtotal':                str(subtotal),
            'discount':                str(discount),
            'subtotal_net':            str(subtotal_net),
            'tax_included':            str(tax),
            'shipping_cost':           None,
            'total':                   str(subtotal_net),
            'free_shipping_threshold': str(threshold) if threshold else None,
            'free_shipping_remaining': str(free_remaining) if free_remaining else None,
            'free_shipping_applied':   bool(
                (threshold and subtotal_net >= threshold) or
                (self.voucher_id and self.voucher.voucher_type == 'FREE_SHIPPING')
            ),
            'item_count': self.items.count(),
        }

    def merge(self, other_cart: 'Cart') -> None:
        with transaction.atomic():
            for other_item in other_cart.items.select_related('variant__product').all():
                existing = self.items.filter(variant=other_item.variant).first()
                if existing:
                    existing.quantity  += other_item.quantity
                    # variant puede ser None para productos sin variantes
                    existing.unit_price = (
                        other_item.variant.effective_price()
                        if other_item.variant
                        else other_item.product.price
                    )
                    existing.save(update_fields=['quantity', 'unit_price', 'updated_at'])
                else:
                    other_item.cart = self
                    other_item.save(update_fields=['cart', 'updated_at'])
            other_cart.delete()


class CartItem(TimeStampedModel):
    """
    Item dentro del carrito. UC-CART-01/02/03.
    unit_price NO es snapshot — se actualiza al precio vigente en cada GET.
    """
    cart       = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant    = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.CASCADE, related_name='cart_items',
    )
    product    = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity   = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table          = 'cart_cart_item'
        verbose_name      = 'Item de carrito'
        # MariaDB no soporta UniqueConstraint con condition (W036) — la
        # constraint no existe a nivel de BD. La unicidad se garantiza a
        # nivel de aplicación: CartView.post() y CartItemListView.post()
        # usan get_or_create(cart, product, variant) dentro de
        # transaction.atomic(), lo que hace imposible crear duplicados.
        # W036 silenciado via SILENCED_SYSTEM_CHECKS en base.py (T-DEV-3).
        constraints       = [
            # Productos con variante: (cart, variant) único.
            models.UniqueConstraint(
                fields=['cart', 'variant'],
                condition=Q(variant__isnull=False),
                name='unique_cart_variant',
            ),
            # Productos sin variante: NULL != NULL en SQL — unique_together
            # no protegía este caso. Restricción explícita sobre (cart, product).
            models.UniqueConstraint(
                fields=['cart', 'product'],
                condition=Q(variant__isnull=True),
                name='unique_cart_product_no_variant',
            ),
        ]

    def __str__(self):
        label = self.variant.option.label if self.variant else self.product.name
        return f'{self.product.name} ({label}) ×{self.quantity}'

    def get_subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    def current_price(self) -> Decimal:
        if self.variant:
            return self.variant.effective_price()
        return self.product.price

    def is_available(self) -> bool:
        # H-CICLO42-01: verificar is_active e is_published del producto antes
        # de evaluar el stock. Sin esta guardia, un producto desactivado aparece
        # como disponible en el carrito y puede llegar al checkout.
        if not (self.product.is_active and self.product.is_published):
            return False
        if self.variant:
            return self.variant.is_available() and self.variant.stock >= self.quantity
        return self.product.stock >= self.quantity

    def available_stock(self) -> int:
        if self.variant:
            return self.variant.stock
        return self.product.stock


class SavedCart(TimeStampedModel):
    """
    Carrito guardado para después. UC-CART-05.
    updated_at (ex saved_at) registra cuándo se guardó por última vez.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='saved_cart',
    )

    class Meta:
        db_table     = 'cart_saved_cart'
        verbose_name = 'Carrito guardado'

    def __str__(self):
        return f'Carrito guardado de {self.user.email}'


class SavedCartItem(TimeStampedModel):
    """Item dentro del carrito guardado."""
    saved_cart    = models.ForeignKey(SavedCart, on_delete=models.CASCADE, related_name='items')
    product       = models.ForeignKey('catalogue.Product', on_delete=models.CASCADE)
    quantity      = models.PositiveIntegerField(default=1)
    price_at_save = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table     = 'cart_saved_cart_item'
        constraints  = [
            models.UniqueConstraint(
                fields=['saved_cart', 'product'],
                name='unique_saved_cart_item',
            )
        ]
        verbose_name = 'Item guardado'

    def __str__(self):
        return f'{self.product.name} ×{self.quantity}'
