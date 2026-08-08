"""Modelo ``WishlistItem`` — addon ``website_sale_wishlist``.

Hogar fiel de la lista de deseos del comprador. En Odoo la wishlist del
storefront la provee el módulo ``website_sale_wishlist`` (modelo
``product.wishlist``); no existe un módulo ``wishlist`` a secas. Este
``WishlistItem`` es la contraparte: satélite de lectura del catálogo (FK string
a ``product.ProductProduct`` — la **variante**, como el ``product_id`` de
``product.wishlist`` en odoo19c :16), sin FK-in, que guarda el
interés del comprador y el precio al momento de agregar (``price_at_add``).

Identifiers + field names in English per DEC-DOC-005.
"""
from decimal import Decimal
from django.conf import settings
from django.db import models
from addons.base.models import SoftDeleteModel, TimeStampedModel
from addons.stock.services import InventoryService


class WishlistItem(TimeStampedModel, SoftDeleteModel):
    """
    Item en la lista de deseos de un comprador. UC-WISH-01/02/03.
    Unico por (user, product) — donde ``product`` es la **variante**
    (``product.product``), igual que el ``product_id`` de ``product.wishlist``
    en la referencia, cuya restriccion es ``UNIQUE(product_id, partner_id)``
    (odoo19c: ``website_sale_wishlist/models/product_wishlist.py:11``).
    price_at_add: precio en el momento de agregar (informativo, no snapshot de orden).

    Hereda SoftDeleteModel (DEC-DOC-007): un item eliminado conserva
    historial para metricas de interes / re-marketing.
    """
    user          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    product       = models.ForeignKey(
        'product.ProductProduct', on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    price_at_add  = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'wishlist_item'
        # Al colapsar el eje ``variant`` (H-API-213) la clave vuelve a ser
        # simple y **sin** columna nullable, así que las dos UniqueConstraint
        # condicionales de H-CICLO45-01 dejan de hacer falta: existían sólo
        # porque ``variant=NULL`` no participa de un UNIQUE en SQL
        # (``NULL != NULL``). Un UNIQUE plano sí lo aplica la BD, así que la
        # carrera que el pre-check de la vista cubría a mano ya no existe.
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_wishlist_user_product',
            ),
        ]
        ordering     = ['-created_at']
        verbose_name = 'Item de lista de deseos'

    def __str__(self):
        return f'{self.user.login} → {self.product}'

    @property
    def current_price(self) -> Decimal:
        return self.product.lst_price

    @property
    def price_changed(self) -> bool:
        return self.current_price != self.price_at_add

    @property
    def is_available(self) -> bool:
        return (self.product.active
                and InventoryService.available_quantity(self.product) > 0)
