"""``hr.employee`` / ``hr.employee.public`` — los coches del empleado.

Adaptación de Odoo hr_fleet/models/employee.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 95 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 9 símbolos de ``HrEmployee`` + 1 de
``HrEmployeePublic``
=====================================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``employee_cars_count`` (``:12``)                            property
``car_ids`` (``:13-16``)                                     accesor inverso
                                                             (ver abajo)
``license_plate`` (``:17``)                                  property
``mobility_card`` (``:18``)                                  columna (campos)
``action_open_employee_cars`` (``:20-30``)                   NO portado (ver
                                                             "Lo que no se
                                                             porta")
``_compute_license_plate`` (``:32-38``)                      método verbatim
``_search_license_plate`` (``:40-43``)                       classmethod
                                                             verbatim
``_compute_employee_cars_count`` (``:45-51``)                método verbatim
``_check_work_contact_id`` (``:53-61``)                      método + receptor
                                                             ``pre_save``
``write`` (``:63-92``)                                       receptores
                                                             ``pre_save``/
                                                             ``post_save``
``HrEmployeePublic.mobility_card`` (``:95``)                 property de
                                                             delegación
===========================================================  ==================

``car_ids`` no se agrega aquí — es el accesor inverso de
``FleetVehicle.driver_employee`` (``related_name='car_ids'``), que
``fleet_vehicle.py`` de este mismo addon declara. ``employee.car_ids.all()``
es el equivalente de ``employee.car_ids``.

Lo que no se porta — y por qué
================================

**``action_open_employee_cars`` es navegación pura** — devuelve un
diccionario ``ir.actions.act_window`` con vistas XML de este addon. Sin
``ir.actions`` ni vistas en este stack (DRF headless), mismo criterio que
``account_fleet/models/fleet_vehicle.py`` declara para
``action_view_bills``. El dato de negocio que la acción listaba está
disponible: ``FleetVehicleAssignationLog.objects.filter(driver_employee=e,
driver=e.work_contact)``.

Divergencias declaradas
=========================

1. **``groups=`` no se porta** (``employee_cars_count``, ``car_ids``,
   ``license_plate``, ``mobility_card``) — no hay usuario ambiente en la
   capa de modelo; el gate de autorización (DEC-11, ``HasCapability``) es de
   la vista DRF (mismo criterio que ``account_fleet``, divergencia 1).
2. **``@api.constrains('work_contact_id')`` → receptor ``pre_save``** — el
   gancho de constraint de Odoo no existe; la validación corre en
   ``pre_save`` de ``hr.employee`` (falla ruidoso ANTES de persistir, la
   misma ventana que el constrains).
3. **``write`` → par ``pre_save``/``post_save``** — sin ``vals`` dict, el
   "cambió el contacto de trabajo / la tarjeta de movilidad" se mide
   comparando contra el valor previo en BD (``pre_save`` lo captura en el
   instance) y la propagación a los vehículos corre en ``post_save`` —
   después del guardado, como el ``write`` de la referencia ("needs to be
   done after because of _sync_user").
4. **``Domain.NEGATIVE_OPERATORS`` → sin rama negativa** —
   ``_search_license_plate`` devuelve el ``Q`` positivo; quien necesite el
   negativo lo niega con ``~`` (la referencia devolvía ``NotImplemented``
   para que el motor de dominios lo hiciera — aquí el motor es ``Q``).
5. **``sudo()`` → acceso directo** — sin usuario ambiente no hay elevación.
"""
import fields
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from addons.fleet.models import FleetVehicle, FleetVehicleAssignationLog
from addons.hr.models.hr_employee import HrEmployee
from exceptions import ValidationError
from orm.model_classes import extend_model
from orm.models import Q
from tools.translate import _


def _compute_license_plate(self):
    """≙ ``_compute_license_plate``
    (``odoo19c: hr_fleet/models/employee.py:32-38``) — las placas de los
    vehículos del empleado más la de su coche particular, separadas por
    espacio."""
    car_plates = [
        plate for plate in self.car_ids.values_list('license_plate', flat=True)
        if plate
    ]
    if self.private_car_plate:
        return ' '.join(car_plates + [self.private_car_plate])
    return ' '.join(car_plates) or self.private_car_plate


def _search_license_plate(cls, value, lookup='icontains'):
    """≙ ``_search_license_plate`` (``:40-43``) — el ``Q`` que busca por
    placa de vehículo asignado O placa del coche particular. Divergencia 4:
    sin rama de operadores negativos (negar con ``~``)."""
    return (Q(**{f'car_ids__license_plate__{lookup}': value})
            | Q(**{f'private_car_plate__{lookup}': value}))


def _compute_employee_cars_count(self):
    """≙ ``_compute_employee_cars_count`` (``:45-51``) — cuántas entradas
    del historial de asignación apuntan a este empleado (y a su contacto de
    trabajo, el mismo doble filtro de la referencia)."""
    if self.pk is None:
        return 0
    return FleetVehicleAssignationLog.objects.filter(
        driver_employee=self, driver=self.work_contact,
    ).count()


def employee_cars_count(self):
    """≙ ``employee_cars_count`` (``:12``, compute sin store)."""
    return self._compute_employee_cars_count()


def license_plate(self):
    """≙ ``license_plate`` (``:17``, compute sin store + search)."""
    return self._compute_license_plate()


def _check_work_contact_id(self):
    """≙ ``_check_work_contact_id`` (``:53-61``) — veta quitar el contacto
    de trabajo a un empleado con coches vinculados. Divergencia 2: corre en
    ``pre_save`` en vez de ``@api.constrains``."""
    if self.work_contact_id is not None or self.pk is None:
        return
    if FleetVehicle.objects.filter(driver_employee=self).exists():
        raise ValidationError(
            _('Cannot remove address from employees with linked cars.'),
        )


@receiver(pre_save, sender=HrEmployee,
          dispatch_uid='hr_fleet.employee_pre_save_capture_and_check')
def _employee_pre_save(sender, instance, **kwargs):
    """La mitad previa del ``write`` de la referencia (``:63-66``) + el
    constrains (divergencias 2 y 3): valida el contacto de trabajo y
    captura los valores previos que ``post_save`` compara."""
    instance._check_work_contact_id()
    instance._hr_fleet_old_work_contact_id = None
    instance._hr_fleet_old_mobility_card = None
    if instance.pk is not None:
        previous = (HrEmployee.objects.filter(pk=instance.pk)
                    .values('work_contact_id', 'mobility_card').first())
        if previous:
            instance._hr_fleet_old_work_contact_id = previous['work_contact_id']
            instance._hr_fleet_old_mobility_card = previous['mobility_card']


@receiver(post_save, sender=HrEmployee,
          dispatch_uid='hr_fleet.employee_post_save_sync_cars')
def _employee_post_save(sender, instance, created, **kwargs):
    """La mitad posterior del ``write`` de la referencia (``:68-92``) —
    propaga el cambio de contacto de trabajo a los vehículos (conductor
    actual y futuro) y refresca su tarjeta de movilidad."""
    if created:
        return
    old_work_contact_id = getattr(instance, '_hr_fleet_old_work_contact_id', None)
    old_mobility_card = getattr(instance, '_hr_fleet_old_mobility_card', None)

    if instance.work_contact_id != old_work_contact_id:
        cars = FleetVehicle.objects.filter(
            Q(driver_employee=instance) | Q(future_driver_employee=instance),
        )
        new_work_contact = (instance.work_contact
                            if instance.work_contact_id else None)
        cars.filter(driver_employee=instance).update(driver=new_work_contact)
        cars.filter(future_driver_employee=instance).update(
            future_driver=new_work_contact,
        )

    if instance.mobility_card != old_mobility_card:
        for car in FleetVehicle.objects.filter(driver_employee=instance):
            car._compute_mobility_card()
            car.save(update_fields=['mobility_card'])


def mobility_card_public(self):
    """≙ ``HrEmployeePublic.mobility_card`` (``:95``, ``readonly=True``) —
    delega en el empleado, como el resto de la ficha pública local."""
    return self.employee_id.mobility_card if self.employee_id_id else ''


def apply_hr_fleet_employee_extensions():
    """Cuelga sobre ``hr.employee`` (y su ficha pública) lo que
    ``hr_fleet`` necesita — ≙ ``_inherit``. Se invoca desde
    ``HrFleetConfig.ready()``. Los receptores de señal de arriba se
    conectan al importar este módulo (``ready()`` ya lo importa una vez;
    ``dispatch_uid`` los hace idempotentes)."""
    extend_model(
        'hr', 'HrEmployee',
        campos={
            'mobility_card': fields.Char(
                blank=True, default='',
                verbose_name='Tarjeta de movilidad',
                help_text='Odoo mobility_card (su groups= no se porta — '
                          'divergencia 1 del docstring del módulo).',
            ),
        },
        metodos={
            '_compute_license_plate': _compute_license_plate,
            '_search_license_plate': classmethod(_search_license_plate),
            '_compute_employee_cars_count': _compute_employee_cars_count,
            '_check_work_contact_id': _check_work_contact_id,
        },
        propiedades={
            'employee_cars_count': employee_cars_count,
            'license_plate': license_plate,
        },
    )
    extend_model(
        'hr', 'HrEmployeePublic',
        propiedades={
            'mobility_card': mobility_card_public,
        },
    )
