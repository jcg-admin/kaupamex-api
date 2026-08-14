"""``fleet.vehicle.odometer`` — bitácora de odómetro (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_odometer.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

NO se porta ``_onchange_vehicle`` — es un ``@api.onchange`` de formulario
(recalcula ``unit`` en el cliente antes de guardar); aquí ``unit`` ya es una
``@property`` siempre en vivo, así que no hay nada que sincronizar.
"""
import fields
import models

from addons.base.models import TimeStampedModel


class FleetVehicleOdometer(TimeStampedModel):
    """``fleet.vehicle.odometer`` — una lectura de odómetro con fecha."""

    date = fields.Date(null=True, blank=True, help_text='Odoo date (default hoy).')
    value = fields.Float(
        default=0, help_text='Lectura del odómetro (Odoo value, aggregator=max).',
    )
    vehicle = fields.Many2one(
        'fleet.FleetVehicle', on_delete=models.CASCADE,
        related_name='odometer_logs', help_text='Odoo vehicle_id (required).',
    )
    driver = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_odometer_logs',
        help_text='Conductor al momento de la lectura (Odoo driver_id, '
                   'compute+store — aquí sincronizado en save() si no viene dado).',
    )

    class Meta:
        db_table = 'fleet_vehicle_odometer'
        ordering = ['-date']
        verbose_name = 'Lectura de odómetro'
        verbose_name_plural = 'Lecturas de odómetro'

    def __str__(self):
        """``_compute_vehicle_log_name`` — "Vehículo / fecha"."""
        vehicle_name = self.vehicle.name if self.vehicle_id else ''
        if not vehicle_name:
            return str(self.date) if self.date else ''
        if self.date:
            return f'{vehicle_name} / {self.date}'
        return vehicle_name

    @property
    def unit(self):
        """``related='vehicle_id.odometer_unit', readonly=True``."""
        return self.vehicle.odometer_unit if self.vehicle_id else None

    def save(self, *args, **kwargs):
        """``_compute_driver_id`` — si no viene dado, hereda el conductor
        actual del vehículo (sólo si aún no tiene uno asignado)."""
        if not self.driver_id and self.vehicle_id and self.vehicle.driver_id:
            self.driver = self.vehicle.driver
        super().save(*args, **kwargs)
