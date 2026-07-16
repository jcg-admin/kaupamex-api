"""Models — apps.addons.wishlist (Sprint 14)."""
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.core.models import SoftDeleteModel, TimeStampedModel



class WishlistItem(TimeStampedModel, SoftDeleteModel):
    """
    Item en la lista de deseos de un comprador. UC-WISH-01/02/03.
    Unico por (user, product, variant).
    variant es nullable para productos sin variantes.
    price_at_add: precio en el momento de agregar (informativo, no snapshot de orden).

    Hereda SoftDeleteModel (DEC-DOC-007): un item eliminado conserva
    historial para metricas de interes / re-marketing.
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
        db_table = 'wishlist_item'
        # H-CICLO45-01: unique_together no protege columnas NULL en SQL
        # (NULL != NULL semantics). Un producto sin variante tiene variant=NULL;
        # dos peticiones concurrentes pueden crear filas duplicadas
        # (user, product, NULL) porque el constraint de BD no las detecta.
        # Reemplazado por dos UniqueConstraint condicionales (igual que CartItem):
        #   - con variante: (user, product, variant) cuando variant IS NOT NULL
        #   - sin variante: (user, product) cuando variant IS NULL
        # MariaDB no soporta UniqueConstraint con condition (W036) — la
        # constraint no existe a nivel de BD. La unicidad se garantiza a
        # nivel de aplicación: WishlistView.post() hace pre-check con
        # all_objects.filter(user, product, variant) y captura IntegrityError
        # como fallback contra race conditions, retornando 409 en ambos casos.
        # W036 silenciado via SILENCED_SYSTEM_CHECKS en base.py (T-DEV-4).
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product', 'variant'],
                condition=Q(variant__isnull=False),
                name='unique_wishlist_user_product_variant',
            ),
            models.UniqueConstraint(
                fields=['user', 'product'],
                condition=Q(variant__isnull=True),
                name='unique_wishlist_user_product_no_variant',
            ),
        ]
        ordering     = ['-created_at']
        verbose_name = 'Item de lista de deseos'

    def __str__(self):
        label = self.variant.option.label if self.variant else self.product.name
        return f'{self.user.email} → {self.product.name} ({label})'

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
