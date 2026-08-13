"""``fleet.vehicle.model.category`` — categoría de modelo (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_model_category.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import fields
import models

from addons.base.models import TimeStampedModel


class FleetVehicleModelCategory(TimeStampedModel):
    """``fleet.vehicle.model.category`` — p. ej. "Sedán", "SUV", "Pickup"."""

    name = fields.Char(max_length=150, unique=True, help_text='Odoo name (unique).')
    sequence = fields.Integer(default=0, help_text='Orden en el kanban (Odoo sequence).')

    class Meta:
        db_table = 'fleet_vehicle_model_category'
        ordering = ['sequence', 'id']
        verbose_name = 'Categoría de modelo de vehículo'
        verbose_name_plural = 'Categorías de modelo de vehículo'
        constraints = [
            models.UniqueConstraint(fields=['name'], name='fleet_model_category_name_uniq'),
        ]

    def __str__(self):
        return self.name or ''
