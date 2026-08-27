"""``fleet.vehicle.odometer`` — el conductor de la lectura, como empleado.

Adaptación de Odoo hr_fleet/models/fleet_vehicle_odometer.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 13 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte — 1 símbolo de la referencia: ``driver_employee_id``
(``related='vehicle_id.driver_employee_id'``, ``readonly=True``,
``:11-13``) → property ``driver_employee``. DIVERGENCIA declarada: el
``related`` no almacenado es property — mismo criterio que
``odometer_unit`` del propio ``fleet_vehicle_log_services.py`` local.
"""
from orm.model_classes import extend_model


def driver_employee(self):
    """≙ ``driver_employee_id`` (``related='vehicle_id.driver_employee_id'``,
    ``'Driver (Employee)'``, ``readonly=True``)."""
    return self.vehicle.driver_employee if self.vehicle_id else None


def apply_hr_fleet_fleet_vehicle_odometer_extensions():
    """Cuelga sobre ``fleet.vehicle.odometer`` lo que ``hr_fleet``
    necesita — ≙ ``_inherit``. Se invoca desde ``HrFleetConfig.ready()``."""
    extend_model(
        'fleet', 'FleetVehicleOdometer',
        propiedades={
            'driver_employee': driver_employee,
        },
    )
