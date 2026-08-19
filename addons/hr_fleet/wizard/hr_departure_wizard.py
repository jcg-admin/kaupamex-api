"""``hr.departure.wizard`` — liberar el coche de empresa al dar de baja.

Adaptación de Odoo hr_fleet/wizard/hr_departure_wizard.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 30 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 símbolos de la referencia
=========================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``release_campany_car`` (``:9``)                             kwarg del método
                                                             envuelto + default
                                                             ``_default_release_campany_car``
``action_register_departure`` (``:11-15``)                   envoltura del
                                                             classmethod de
                                                             ``hr``
``_free_company_car`` (``:17-30``)                           classmethod
                                                             verbatim
===========================================================  ==================

Divergencias declaradas
=========================

1. **El campo del wizard es un argumento** — el ``hr.departure.wizard``
   local es una clase sin tabla cuyos campos son argumentos de
   ``action_register_departure`` (patrón declarado en su propio docstring);
   ``release_campany_car`` sigue ese camino como kwarg keyword-only. El
   nombre conserva el typo de la referencia (*campany*) — es el símbolo, no
   se "corrige" (mismo criterio que reproducir la forma de la fuente).
2. **``default=lambda self: self.env.user.has_group(…)`` →
   ``_default_release_campany_car(user)``** — sin usuario ambiente ni
   lambdas serializables (reglas 1 y 3 de la tanda), el default es un
   classmethod que el llamador consulta con SU usuario.
3. **Envoltura manual, no ``chain_method``** — el override AÑADE un kwarg
   que la firma base no acepta; el relevo de ``chain_method`` pasa
   argumentos idénticos a ambas implementaciones y reventaría. La
   envoltura llama al original primero y libera después — el mismo orden
   ``action = super(); …; return action`` de la referencia. Idempotente
   por marca (``ready()`` puede correr dos veces).
4. **``cars.write({...})`` → ``save()`` por vehículo** — el ``update()``
   masivo de Django salta las señales; el ``save()`` fila a fila deja que
   el ``pre_save`` de ``fleet_vehicle.py`` (este addon) recalcule
   ``mobility_card``, igual que el recompute de ``@api.depends`` que el
   ``write`` de la referencia dispara.
"""
import functools

from addons.fleet.models import FleetVehicle, FleetVehicleAssignationLog
from addons.hr.wizard.hr_departure_wizard import HrDepartureWizard
from orm.models import Q


def _default_release_campany_car(cls, user):
    """≙ el ``default`` de ``release_campany_car``
    (``odoo19c: hr_fleet/wizard/hr_departure_wizard.py:9``) — si el usuario
    dado pertenece al grupo de flota (divergencia 2)."""
    return user.has_group('fleet.fleet_group_user')


def _free_company_car(cls, employees, departure_date):
    """≙ ``_free_company_car`` (``:17-30``): cierra en ``departure_date``
    los registros del historial de asignación de los empleados (los sin
    fecha fin o con fin posterior a la baja) y desasigna sus vehículos
    (conductor y empleado a ``None``)."""
    driver_partner_pks = set()
    for employee in employees:
        user = employee.user
        if user is not None and user.partner_id:
            driver_partner_pks.add(user.partner_id)
        if employee.work_contact_id:
            driver_partner_pks.add(employee.work_contact_id)
    if not driver_partner_pks:
        return
    FleetVehicleAssignationLog.objects.filter(
        Q(date_end__isnull=True) | Q(date_end__gt=departure_date),
        driver_id__in=driver_partner_pks,
    ).update(date_end=departure_date)
    for car in FleetVehicle.objects.filter(driver_id__in=driver_partner_pks):
        car.driver = None
        car.driver_employee = None
        car.save(update_fields=['driver', 'driver_employee', 'mobility_card'])


def apply_hr_fleet_hr_departure_wizard_extensions():
    """Envuelve ``action_register_departure`` y cuelga los dos classmethods
    nuevos sobre ``hr.departure.wizard`` — ≙ ``_inherit``. Se invoca desde
    ``HrFleetConfig.ready()``."""
    raw = HrDepartureWizard.__dict__['action_register_departure']
    original = raw.__func__ if isinstance(raw, classmethod) else raw
    if getattr(original, '_hr_fleet_wrapped', False):
        return

    @functools.wraps(original)
    def action_register_departure(cls, employees, departure_reason,
                                  departure_date, *args,
                                  release_campany_car=False, **kwargs):
        """≙ ``action_register_departure`` (``:11-15``) — registra la baja
        (implementación de ``hr``) y, si se pidió, libera el coche de
        empresa. Orden verbatim: primero el ``super()``, después la
        liberación."""
        action = original(cls, employees, departure_reason, departure_date,
                          *args, **kwargs)
        if release_campany_car:
            cls._free_company_car(employees, departure_date)
        return action

    action_register_departure._hr_fleet_wrapped = True
    HrDepartureWizard.action_register_departure = classmethod(
        action_register_departure,
    )
    if not hasattr(HrDepartureWizard, '_free_company_car'):
        HrDepartureWizard._free_company_car = classmethod(_free_company_car)
    if not hasattr(HrDepartureWizard, '_default_release_campany_car'):
        HrDepartureWizard._default_release_campany_car = classmethod(
            _default_release_campany_car,
        )
