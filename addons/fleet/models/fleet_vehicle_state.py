"""``fleet.vehicle.state`` — estado configurable del vehículo (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_vehicle_state.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

DEFERIDO (no stub): la referencia siembra datos demo con external IDs fijos
(``fleet.fleet_vehicle_state_new_request``, ``fleet_vehicle_state_waiting_list``)
usados como default de ``fleet.vehicle.state_id`` y en la lógica de
``create()``/``write()`` de ``FleetVehicle`` (cambio de conductor futuro). Sin
un fixture/seed de datos que reproduzca esos registros con un identificador
estable, ``FleetVehicle`` no fija un ``_get_default_state()`` ni replica esas
ramas — ver el docstring de ``fleet_vehicle.py``.
"""
import fields

from addons.base.models import TimeStampedModel


class FleetVehicleState(TimeStampedModel):
    """``fleet.vehicle.state`` — columna del kanban de vehículos (p. ej.

    "Nueva solicitud", "En lista de espera", "Activo", "Vendido")."""

    name = fields.Char(
        max_length=150, unique=True,
        help_text='Nombre del estado (Odoo name, translate=True en la '
                   'referencia; i18n no portado).',
    )
    sequence = fields.Integer(default=0, help_text='Orden del kanban (Odoo sequence).')
    fold = fields.Boolean(
        default=False,
        help_text='Columna plegada en el kanban (Odoo fold).',
    )

    class Meta:
        db_table = 'fleet_vehicle_state'
        ordering = ['sequence']
        verbose_name = 'Estado de vehículo'
        verbose_name_plural = 'Estados de vehículo'

    def __str__(self):
        return self.name or ''
