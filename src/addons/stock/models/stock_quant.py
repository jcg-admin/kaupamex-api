"""Modelo ``StockQuant`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.quant`` (``stock/models/stock_quant.py``, idéntico
en 18 y 19): existencia de un producto en una ubicación. Núcleo verificado en
ambas versiones — ``product_id``/``location_id``/``quantity`` (a la mano)/
``reserved_quantity``. Expone los helpers que ``stock.move`` usa para reservar
(``available_qty``) y para aplicar un movimiento hecho (``apply_move``).
"""
from decimal import Decimal

import fields
import models
from django.utils import timezone

from addons.base.models import TimeStampedModel


class StockQuant(TimeStampedModel):
    """``stock.quant`` — existencia de un producto en una ubicación."""

    product           = fields.Many2one(
        'catalogue.Product', on_delete=models.CASCADE, related_name='quants',
        help_text='Producto (Odoo product_id).',
    )
    location          = fields.Many2one(
        'stock.StockLocation', on_delete=models.CASCADE, related_name='quants',
        help_text='Ubicación (Odoo location_id).',
    )
    quantity          = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad a la mano (Odoo stock.quant.quantity).',
    )
    reserved_quantity = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad reservada (Odoo reserved_quantity).',
    )
    lot               = fields.Many2one(
        'stock.StockLot', on_delete=models.CASCADE, related_name='quants',
        null=True, blank=True,
        help_text='Lote / número de serie (Odoo lot_id). NULL = sin lote.',
    )
    in_date           = fields.Datetime(
        default=timezone.now,
        help_text='Fecha de entrada al quant (Odoo stock.quant.in_date; '
                  'clave de orden de la estrategia FIFO).',
    )

    class Meta:
        db_table = 'stock_quant'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'location', 'lot'],
                name='unique_quant_product_location_lot',
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
        agg = cls.objects.filter(product=product, location=location).aggregate(
            q=models.Sum('quantity'), r=models.Sum('reserved_quantity'),
        )
        on_hand = agg['q'] if agg['q'] is not None else Decimal('0.00')
        reserved = agg['r'] if agg['r'] is not None else Decimal('0.00')
        return on_hand - reserved

    @classmethod
    def gather(cls, product, location, removal_strategy='fifo'):
        """Devuelve los quants del producto en ``location`` ordenados por estrategia.

        Réplica de ``stock.quant._gather`` + ``_get_removal_strategy_order`` de
        Odoo (idéntico 18/19). El orden de remoción de la **base** ``stock`` es:

        - ``fifo`` → ``in_date, id`` (lo más antiguo primero).
        - ``lifo`` → ``-in_date, id`` (lo más reciente primero).

        La estrategia ``fefo`` la añade el satélite ``product_expiry``
        (ordena por ``removal_date``); no vive en la base.
        """
        qs = cls.objects.filter(product=product, location=location, quantity__gt=0)
        if removal_strategy == 'lifo':
            return qs.order_by('-in_date', 'id')
        return qs.order_by('in_date', 'id')

    @classmethod
    def apply_move(cls, product, location_src, location_dest, qty) -> None:
        """Aplica un movimiento hecho: resta del origen, suma al destino.

        Réplica del efecto de ``_action_done`` sobre los quants (Odoo
        ``_update_available_quantity``). Las ubicaciones no-internas no llevan
        contabilidad de quant (son sumideros/fuentes).
        """
        qty = Decimal(qty)
        if not location_src.should_bypass_reservation():
            src, _ = cls.objects.get_or_create(
                product=product, location=location_src, lot=None)
            src.quantity = src.quantity - qty
            src.save(update_fields=['quantity', 'updated_at'])
        if not location_dest.should_bypass_reservation():
            dest, _ = cls.objects.get_or_create(
                product=product, location=location_dest, lot=None)
            dest.quantity = dest.quantity + qty
            dest.save(update_fields=['quantity', 'updated_at'])

    @classmethod
    def set_on_hand(cls, product, location, qty, lot=None):
        """Ajuste de inventario: fija la cantidad a la mano (Odoo inventory)."""
        quant, _ = cls.objects.get_or_create(product=product, location=location, lot=lot)
        quant.quantity = Decimal(qty)
        quant.save(update_fields=['quantity', 'updated_at'])
        return quant
