"""Modelo ``StockLocation`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.location`` (``stock/models/stock_location.py``,
idéntico en 18 y 19): ubicación de inventario. Núcleo verificado en ambas
versiones — ``name``/``usage`` (``supplier``/``view``/``internal``/``customer``/
``inventory``/``production``/``transit``, o19:32-39)/``location_id`` (padre,
self-FK). ``complete_name`` se calcula recursivamente.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class StockLocation(TimeStampedModel):
    """``stock.location`` — ubicación de inventario."""

    USAGE_SUPPLIER   = 'supplier'
    USAGE_VIEW       = 'view'
    USAGE_INTERNAL   = 'internal'
    USAGE_CUSTOMER   = 'customer'
    USAGE_INVENTORY  = 'inventory'
    USAGE_PRODUCTION = 'production'
    USAGE_TRANSIT    = 'transit'
    USAGE_CHOICES = [
        (USAGE_SUPPLIER, 'Proveedor'),
        (USAGE_VIEW, 'Virtual'),
        (USAGE_INTERNAL, 'Interna'),
        (USAGE_CUSTOMER, 'Cliente'),
        (USAGE_INVENTORY, 'Pérdida de inventario'),
        (USAGE_PRODUCTION, 'Producción'),
        (USAGE_TRANSIT, 'Tránsito'),
    ]

    name        = fields.Char(
        max_length=100, help_text='Nombre de la ubicación (Odoo stock.location.name).',
    )
    usage       = fields.Selection(
        max_length=16, choices=USAGE_CHOICES, default=USAGE_INTERNAL,
        help_text='Tipo de ubicación (Odoo stock.location.usage).',
    )
    location    = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='child_ids', help_text='Ubicación padre (Odoo location_id).',
    )

    class Meta:
        db_table = 'stock_location'
        ordering = ['name']
        verbose_name = 'Ubicación de inventario'
        verbose_name_plural = 'Ubicaciones de inventario'

    def __str__(self) -> str:
        return self.complete_name()

    def complete_name(self) -> str:
        """Nombre completo jerárquico (Odoo complete_name)."""
        if self.location is not None:
            return f'{self.location.complete_name()}/{self.name}'
        return self.name

    def should_bypass_reservation(self) -> bool:
        """Ubicaciones no-internas no reservan stock (Odoo _should_bypass_reservation)."""
        return self.usage in (
            self.USAGE_SUPPLIER, self.USAGE_CUSTOMER,
            self.USAGE_INVENTORY, self.USAGE_PRODUCTION,
        )
