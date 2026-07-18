"""Modelo ``StockQuant`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.quant`` (``stock/models/stock_quant.py``, idéntico
en 18 y 19): existencia de un producto en una ubicación. Núcleo verificado en
ambas versiones — ``product_id``/``location_id``/``quantity`` (a la mano)/
``reserved_quantity``. Expone los helpers que ``stock.move`` usa para reservar
(``available_qty``) y para aplicar un movimiento hecho (``apply_move``).
"""
from decimal import Decimal

from django.db import models

from core.models import TimeStampedModel


class StockQuant(TimeStampedModel):
    """``stock.quant`` — existencia de un producto en una ubicación."""

    product           = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE, related_name='quants',
        help_text='Producto (Odoo product_id).',
    )
    location          = models.ForeignKey(
        'stock.StockLocation', on_delete=models.CASCADE, related_name='quants',
        help_text='Ubicación (Odoo location_id).',
    )
    quantity          = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad a la mano (Odoo stock.quant.quantity).',
    )
    reserved_quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad reservada (Odoo reserved_quantity).',
    )

    class Meta:
        db_table = 'stock_quant'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'location'], name='unique_quant_product_location',
            ),
        ]
        verbose_name = 'Existencia de inventario'
        verbose_name_plural = 'Existencias de inventario'

    def __str__(self) -> str:
        return f'{self.product}@{self.location}: {self.quantity}'

    @classmethod
    def available_qty(cls, product, location) -> Decimal:
        """Cantidad disponible (a la mano − reservada) en ``location``.

        Réplica de ``_get_available_quantity`` de Odoo. Ubicaciones no-internas
        (proveedor/cliente/producción/inventario) tienen disponibilidad infinita
        para efectos del flujo (``should_bypass_reservation``): devuelve un tope
        alto para no bloquear la reserva desde esas fuentes.
        """
        if location.should_bypass_reservation():
            return Decimal('999999999.00')
        quant = cls.objects.filter(product=product, location=location).first()
        if quant is None:
            return Decimal('0.00')
        return quant.quantity - quant.reserved_quantity

    @classmethod
    def apply_move(cls, product, location_src, location_dest, qty) -> None:
        """Aplica un movimiento hecho: resta del origen, suma al destino.

        Réplica del efecto de ``_action_done`` sobre los quants (Odoo
        ``_update_available_quantity``). Las ubicaciones no-internas no llevan
        contabilidad de quant (son sumideros/fuentes).
        """
        qty = Decimal(qty)
        if not location_src.should_bypass_reservation():
            src, _ = cls.objects.get_or_create(product=product, location=location_src)
            src.quantity = src.quantity - qty
            src.save(update_fields=['quantity', 'updated_at'])
        if not location_dest.should_bypass_reservation():
            dest, _ = cls.objects.get_or_create(product=product, location=location_dest)
            dest.quantity = dest.quantity + qty
            dest.save(update_fields=['quantity', 'updated_at'])

    @classmethod
    def set_on_hand(cls, product, location, qty):
        """Ajuste de inventario: fija la cantidad a la mano (Odoo inventory)."""
        quant, _ = cls.objects.get_or_create(product=product, location=location)
        quant.quantity = Decimal(qty)
        quant.save(update_fields=['quantity', 'updated_at'])
        return quant
