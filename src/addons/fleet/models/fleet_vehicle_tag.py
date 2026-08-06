"""``fleet.vehicle.tag`` — etiqueta libre de vehículo (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_tag.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import fields
import models

from addons.base.models import TimeStampedModel


class FleetVehicleTag(TimeStampedModel):
    """``fleet.vehicle.tag`` — etiqueta M2M aplicable a ``fleet.vehicle``."""

    name = fields.Char(
        max_length=150, unique=True,
        help_text='Nombre de la etiqueta (Odoo name, translate=True en la '
                   'referencia; i18n no portado).',
    )
    color = fields.Integer(default=0, help_text='Índice de color (Odoo color).')

    class Meta:
        db_table = 'fleet_vehicle_tag'
        verbose_name = 'Etiqueta de vehículo'
        verbose_name_plural = 'Etiquetas de vehículo'
        constraints = [
            # ``_name_uniq`` de la fuente.
            models.UniqueConstraint(fields=['name'], name='fleet_vehicle_tag_name_uniq'),
        ]

    def __str__(self):
        return self.name or ''
