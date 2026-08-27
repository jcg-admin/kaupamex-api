"""``fleet.vehicle.log.contract`` — el conductor del contrato, como empleado.

Adaptación de Odoo hr_fleet/models/fleet_vehicle_log_contract.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 23 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte — 2 símbolos de la referencia
=====================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``purchaser_employee_id``                                    property
(``related='vehicle_id.driver_employee_id'``, ``:11-14``)    ``purchaser_employee``
``action_open_employee`` (``:16-23``)                        NO portado
===========================================================  ==================

**``action_open_employee`` es navegación pura** (``ir.actions.act_window``
al formulario del empleado) — mismo criterio que
``fleet_vehicle.py`` de este addon. El dato es
``contract.purchaser_employee``.

DIVERGENCIA declarada: el ``related`` no almacenado es property — mismo
criterio que ``purchaser`` del propio ``fleet_vehicle_log_contract.py``
local (``:144``).
"""
from orm.model_classes import extend_model


def purchaser_employee(self):
    """≙ ``purchaser_employee_id``
    (``related='vehicle_id.driver_employee_id'``, ``'Driver (Employee)'``)."""
    return self.vehicle.driver_employee if self.vehicle_id else None


def apply_hr_fleet_fleet_vehicle_log_contract_extensions():
    """Cuelga sobre ``fleet.vehicle.log.contract`` lo que ``hr_fleet``
    necesita — ≙ ``_inherit``. Se invoca desde ``HrFleetConfig.ready()``."""
    extend_model(
        'fleet', 'FleetVehicleLogContract',
        propiedades={
            'purchaser_employee': purchaser_employee,
        },
    )
