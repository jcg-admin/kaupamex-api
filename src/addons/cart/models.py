"""
Models — addons.cart

Sprint 12 — UC-CART-01/02/03/05/06
Refactorizado en sprint de infraestructura: herencia-modelos-django
  Cart        → TimeStampedModel (refactor puro, sin migración)
  CartItem    → TimeStampedModel (migración 0003: ADD created_at + updated_at)
  SavedCart   → TimeStampedModel (migración 0003: RENAME saved_at→updated_at + ADD created_at)
  SavedCartItem → TimeStampedModel (migración 0003: ADD created_at + updated_at)
"""
from django.conf import settings
from django.db import models
from addons.base.models import TimeStampedModel



# S4 unificación cart→order→sale (analisis-unificar-cart-order-sale):
# los modelos ``Cart`` y ``CartItem`` fueron retirados — en Odoo el carrito
# ES un ``sale.order`` en ``state='draft'`` y sus líneas ``sale.order.line``.
# El carrito vivo es ``orders.Order(status=DRAFT)`` + ``orders.OrderItem``
# (migración de datos + drop de tablas en cart/0002). Este addon conserva
# ``SavedCart``/``SavedCartItem`` (UC-CART-05) y las rutas /api/v1/cart/*
# como fachada del contrato del storefront.


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
