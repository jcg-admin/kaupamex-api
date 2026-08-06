"""``fleet.vehicle.log.services`` — bitácora de servicio (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_log_services.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
from datetime import date

import fields
import models

from addons.base.models import TimeStampedModel
from addons.mail.models import MailThread

from .fleet_vehicle_odometer import FleetVehicleOdometer


class FleetVehicleLogServices(MailThread, TimeStampedModel):
    """``fleet.vehicle.log.services`` — un servicio realizado a un vehículo."""

    STATE_NEW = 'new'
    STATE_RUNNING = 'running'
    STATE_DONE = 'done'
    STATE_CANCELLED = 'cancelled'
    STATES = [
        (STATE_NEW, 'Nuevo'),
        (STATE_RUNNING, 'En curso'),
        (STATE_DONE, 'Terminado'),
        (STATE_CANCELLED, 'Cancelado'),
    ]

    active = fields.Boolean(default=True, help_text='Odoo active.')
    vehicle = fields.Many2one(
        'fleet.FleetVehicle', on_delete=models.CASCADE,
        related_name='log_services', help_text='Odoo vehicle_id (required).',
    )
    amount = fields.Monetary(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text='Odoo amount.',
    )
    description = fields.Char(max_length=255, blank=True, default='', help_text='Odoo description.')
    odometer_log = fields.Many2one(
        'fleet.FleetVehicleOdometer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='service_logs',
        help_text='Odoo odometer_id — lectura de odómetro al momento del '
                   'servicio. Ver la property ``odometer`` para el atajo '
                   'get/set fiel a ``_get_odometer``/``_set_odometer``.',
    )
    date = fields.Date(null=True, blank=True, help_text='Odoo date (default hoy).')
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_service_logs', help_text='Odoo company_id.',
    )
    purchaser = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_service_logs_as_purchaser',
        help_text='Conductor (Odoo purchaser_id, compute+store con default '
                   'vehicle.driver_id — no auto-aplicado; ver sync_defaults).',
    )
    inv_ref = fields.Char(max_length=150, blank=True, default='', help_text='Odoo inv_ref.')
    vendor = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fleet_service_logs_as_vendor', help_text='Odoo vendor_id.',
    )
    notes = fields.Text(blank=True, default='', help_text='Odoo notes.')
    service_type = fields.Many2one(
        'fleet.FleetServiceType', on_delete=models.PROTECT,
        related_name='service_logs', help_text='Odoo service_type_id (required).',
    )
    state = fields.Selection(
        max_length=9, choices=STATES, default=STATE_NEW, help_text='Odoo state.',
    )

    class Meta:
        db_table = 'fleet_vehicle_log_services'
        verbose_name = 'Servicio de vehículo'
        verbose_name_plural = 'Servicios de vehículo'

    def __str__(self):
        return self.service_type.name if self.service_type_id else str(self.pk)

    @property
    def model(self):
        """``related='vehicle_id.model_id', store=True``."""
        return self.vehicle.model if self.vehicle_id else None

    @property
    def brand(self):
        """``related='vehicle_id.model_id.brand_id', store=True``."""
        model = self.model
        return model.brand if model and model.brand_id else None

    @property
    def manager(self):
        """``related='vehicle_id.manager_id', store=True``."""
        return self.vehicle.manager if self.vehicle_id else None

    @property
    def currency(self):
        """``related='company_id.currency_id'``."""
        return self.company.currency if self.company_id else None

    @property
    def odometer_unit(self):
        """``related='vehicle_id.odometer_unit', readonly=True``."""
        return self.vehicle.odometer_unit if self.vehicle_id else None

    # --- odometer: compute+inverse → property con setter -------------------

    @property
    def odometer(self):
        """``_get_odometer``."""
        return self.odometer_log.value if self.odometer_log_id else 0

    @odometer.setter
    def odometer(self, value):
        """``_set_odometer`` — 0/None es un no-op (fiel al ``create()`` de la
        referencia, que descarta un odómetro en 0 al crear). Persiste de
        inmediato (fiel al ``inverse`` de Odoo, que escribe vía el ORM en el
        mismo ciclo) — sólo si el registro ya existe; si aún no se ha
        guardado, el enlace queda en memoria hasta el primer ``save()``.
        """
        if not value:
            return
        log = FleetVehicleOdometer.objects.create(
            value=value, date=self.date or date.today(), vehicle=self.vehicle,
        )
        self.odometer_log = log
        if self.pk:
            self.save(update_fields=['odometer_log'])

    def sync_defaults(self):
        """``_compute_purchaser_id`` — conductor del vehículo si no viene
        dado. NO auto-invocado en ``save()`` (ver ``fleet_vehicle.py`` punto 2)."""
        if self.vehicle_id and not self.purchaser_id:
            self.purchaser = self.vehicle.driver
