"""Models — apps.wishlist (Sprint 14)."""
from decimal import Decimal
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class WishlistItem(TimeStampedModel):
    """
    Item en la lista de deseos de un comprador. UC-WISH-01/02/03.
    Unico por (user, product, variant).
    variant es nullable para productos sin variantes.
    price_at_add: precio en el momento de agregar (informativo, no snapshot de orden).
    """
    user          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    product       = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    variant       = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='wishlist_items',
    )
    price_at_add  = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table        = 'wishlist_item'
        unique_together = [('user', 'product', 'variant')]
        ordering        = ['-created_at']
        verbose_name    = 'Item de lista de deseos'

    def __str__(self):
        label = self.variant.option.label if self.variant else self.product.name
        return f'{self.user.username} → {self.product.name} ({label})'

    @property
    def current_price(self) -> Decimal:
        if self.variant:
            return self.variant.effective_price()
        return self.product.price

    @property
    def price_changed(self) -> bool:
        return self.current_price != self.price_at_add

    @property
    def is_available(self) -> bool:
        if self.variant:
            return self.variant.is_available()
        return self.product.stock > 0 and self.product.is_active and self.product.is_published
