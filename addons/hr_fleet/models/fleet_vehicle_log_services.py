"""``fleet.vehicle.log.services`` — el solicitante del servicio, como
empleado.

Adaptación de Odoo hr_fleet/models/fleet_vehicle_log_services.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 25 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 símbolos de la referencia
=========================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``purchaser_employee_id`` (``:11-14``, compute+store,        columna FK
``readonly=False``)                                          ``purchaser_employee``
``_compute_purchaser_id`` (``:16-21``, override)             encadenado sobre
                                                             ``sync_defaults``
``_compute_purchaser_employee_id`` (``:23-25``)              método verbatim
===========================================================  ==================

Divergencias declaradas
=========================

1. **El ``super()._compute_purchaser_id`` local se llama
   ``sync_defaults``** — medido: el ``fleet`` de este árbol portó
   ``_compute_purchaser_id`` como ``sync_defaults()`` "NO auto-invocado en
   ``save()``" (``fleet/models/fleet_vehicle_log_services.py:129-134``).
   El override de la referencia se encadena ahí con la semántica de relevo
   de ``chain_method``: la aportación de este addon (derivar el conductor
   partner del ``purchaser_employee``) corre primero; la base (conductor
   del vehículo) sólo rellena si ``purchaser`` sigue vacío — su propio
   guard ``if not self.purchaser_id`` la hace inocua cuando este addon ya
   resolvió, que es exactamente el reparto del ``super()`` de la
   referencia.
2. **``_compute_purchaser_employee_id`` no se auto-invoca** — mismo
   contrato que ``sync_defaults`` del ``fleet`` local: quien construya el
   servicio llama ``sync_defaults()`` (que ahora también rellena el
   empleado, ver ``_sync_purchaser_employee``).
"""
import fields
import models

from addons.fleet.models import FleetVehicleLogServices
from orm.method_chain import chain_method
from orm.model_classes import extend_model


def _compute_purchaser_employee_id(self):
    """≙ ``_compute_purchaser_employee_id``
    (``odoo19c: hr_fleet/models/fleet_vehicle_log_services.py:23-25``) — el
    empleado conductor del vehículo del servicio."""
    self.purchaser_employee = (
        self.vehicle.driver_employee if self.vehicle_id else None
    )
    return self.purchaser_employee


def _sync_purchaser_employee(self):
    """≙ el override ``_compute_purchaser_id`` (``:16-21``), en el idioma
    local: si hay ``purchaser_employee``, el conductor partner sale de su
    contacto de trabajo; si no lo hay, se deriva del vehículo — y el relevo
    cae a la base de ``fleet`` (divergencia 1)."""
    if self.purchaser_employee_id is None and self.vehicle_id:
        self._compute_purchaser_employee_id()
    if self.purchaser_employee_id is not None:
        self.purchaser = self.purchaser_employee.work_contact
    return None  # relevo: la base de ``fleet`` (conductor del vehículo) corre después


def apply_hr_fleet_fleet_vehicle_log_services_extensions():
    """Cuelga sobre ``fleet.vehicle.log.services`` lo que ``hr_fleet``
    necesita — ≙ ``_inherit``. Se invoca desde ``HrFleetConfig.ready()``.
    La columna nueva espera su migración en ``fleet/migrations/``."""
    extend_model(
        'fleet', 'FleetVehicleLogServices',
        campos={
            'purchaser_employee': fields.Many2one(
                'hr.HrEmployee', on_delete=models.SET_NULL, null=True,
                blank=True, related_name='fleet_service_logs_as_employee',
                verbose_name='Driver (Employee)',
                help_text='Odoo purchaser_employee_id (compute+store, '
                          'readonly=False — lo rellena sync_defaults).',
            ),
        },
        metodos={
            '_compute_purchaser_employee_id': _compute_purchaser_employee_id,
        },
    )
    chain_method(FleetVehicleLogServices, 'sync_defaults',
                 _sync_purchaser_employee)
