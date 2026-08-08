"""``fleet.vehicle.assignation.log`` — historial de conductor (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_assignation_log.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import fields
import models

from addons.base.models import TimeStampedModel


class FleetVehicleAssignationLog(TimeStampedModel):
    """``fleet.vehicle.assignation.log`` — quién condujo qué vehículo y cuándo."""

    vehicle = fields.Many2one(
        'fleet.FleetVehicle', on_delete=models.CASCADE,
        related_name='assignation_logs', help_text='Odoo vehicle_id (required).',
    )
    driver = fields.Many2one(
        'base.ResPartner', on_delete=models.PROTECT,
        related_name='fleet_assignation_logs', help_text='Odoo driver_id (required).',
    )
    date_start = fields.Date(null=True, blank=True, help_text='Odoo date_start.')
    date_end = fields.Date(null=True, blank=True, help_text='Odoo date_end.')

    class Meta:
        db_table = 'fleet_vehicle_assignation_log'
        ordering = ['-created_at', '-date_start']
        verbose_name = 'Historial de conductor'
        verbose_name_plural = 'Historial de conductores'

    def __str__(self):
        """``_compute_display_name``."""
        vehicle_name = self.vehicle.name if self.vehicle_id else ''
        driver_name = self.driver.name if self.driver_id else ''
        return f'{vehicle_name} - {driver_name}'
