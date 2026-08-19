"""``fleet.vehicle.assignation.log`` — el conductor del historial, como
empleado.

Adaptación de Odoo hr_fleet/models/fleet_vehicle_assignation_log.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 40 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 5 símbolos de la referencia
=========================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``driver_employee_id`` (``:9``, compute+store,               columna FK
``readonly=False``)                                          ``driver_employee``
``attachment_number`` (``:10``, compute)                     property
``_compute_driver_employee_id`` (``:12-24``)                 método verbatim +
                                                             receptor
                                                             ``pre_save``
``_compute_attachment_number`` (``:26-32``)                  método verbatim
``action_get_attachment_view`` (``:34-40``)                  NO portado
===========================================================  ==================

Lo que no se porta — y por qué
================================

**``action_get_attachment_view``** devuelve el ``ir.actions.act_window`` de
``base.action_attachment`` con una vista kanban propia — navegación del
cliente Odoo, sin equivalente DRF (mismo criterio que
``account_fleet/models/fleet_vehicle.py``). El dato queda disponible:
``IrAttachment.objects.filter(res_model='fleet.vehicle.assignation.log',
res_id=log.pk)``.

Divergencias declaradas
=========================

1. **``readonly=False`` del compute+store** — el receptor ``pre_save`` sólo
   deriva el empleado cuando el llamador NO lo fijó él mismo (si
   ``driver_employee`` cambió respecto de BD, se respeta — eso ES el
   ``readonly=False``).
2. **``vehicle_id.company_id`` en el agrupamiento** — verbatim: el empleado
   se resuelve en la empresa del vehículo del log.
"""
import fields
import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from addons.base.models import IrAttachment
from addons.fleet.models import FleetVehicleAssignationLog
from addons.hr.models.hr_employee import HrEmployee
from orm.model_classes import extend_model

#: El ``res_model`` polimórfico con que ``ir.attachment`` cuelga archivos de
#: este modelo — el ``_name`` de la referencia.
ASSIGNATION_LOG_RES_MODEL = 'fleet.vehicle.assignation.log'


def _compute_driver_employee_id(self):
    """≙ ``_compute_driver_employee_id``
    (``odoo19c: hr_fleet/models/fleet_vehicle_assignation_log.py:12-24``) —
    el empleado cuyo contacto de trabajo es el conductor del log, en la
    empresa del vehículo."""
    employee = None
    if self.driver_id:
        vehicle_company_id = (
            self.vehicle.company_id if self.vehicle_id else None
        )
        employee = HrEmployee.objects.filter(
            work_contact_id=self.driver_id, company_id=vehicle_company_id,
        ).first()
    self.driver_employee = employee
    return employee


def _compute_attachment_number(self):
    """≙ ``_compute_attachment_number`` (``:26-32``) — cuántos adjuntos
    cuelgan de este log."""
    if self.pk is None:
        return 0
    return IrAttachment.objects.filter(
        res_model=ASSIGNATION_LOG_RES_MODEL, res_id=self.pk,
    ).count()


def attachment_number(self):
    """≙ ``attachment_number`` (``:10``, ``'Number of Attachments'``,
    compute sin store)."""
    return self._compute_attachment_number()


@receiver(pre_save, sender=FleetVehicleAssignationLog,
          dispatch_uid='hr_fleet.assignation_log_pre_save_driver_employee')
def _assignation_log_pre_save(sender, instance, **kwargs):
    """El ``@api.depends('driver_id')`` del compute almacenado, medido por
    diff contra BD. Respeta un empleado fijado a mano (divergencia 1)."""
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and not (
            set(update_fields) & {'driver', 'driver_employee'}):
        return
    old = {}
    if instance.pk is not None:
        old = (FleetVehicleAssignationLog.objects.filter(pk=instance.pk)
               .values('driver_id', 'driver_employee_id').first()) or {}
    if instance.driver_employee_id != old.get('driver_employee_id'):
        return  # lo fijó el llamador — readonly=False
    if instance.driver_id != old.get('driver_id') or instance.pk is None:
        instance._compute_driver_employee_id()


def apply_hr_fleet_fleet_vehicle_assignation_log_extensions():
    """Cuelga sobre ``fleet.vehicle.assignation.log`` lo que ``hr_fleet``
    necesita — ≙ ``_inherit``. Se invoca desde ``HrFleetConfig.ready()``.
    La columna nueva espera su migración en ``fleet/migrations/``."""
    extend_model(
        'fleet', 'FleetVehicleAssignationLog',
        campos={
            'driver_employee': fields.Many2one(
                'hr.HrEmployee', on_delete=models.SET_NULL, null=True,
                blank=True, related_name='fleet_assignation_logs',
                verbose_name='Driver (Employee)',
                help_text='Odoo driver_employee_id (compute+store, '
                          'readonly=False — lo deriva el receptor pre_save '
                          'cuando el llamador no lo fija).',
            ),
        },
        metodos={
            '_compute_driver_employee_id': _compute_driver_employee_id,
            '_compute_attachment_number': _compute_attachment_number,
        },
        propiedades={
            'attachment_number': attachment_number,
        },
    )
