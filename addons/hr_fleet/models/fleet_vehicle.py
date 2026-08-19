"""``fleet.vehicle`` — el conductor como empleado, sincronizado.

Adaptación de Odoo hr_fleet/models/fleet_vehicle.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 133 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 11 símbolos de la referencia
==========================================================

===========================================================  ==================
Símbolo de la referencia (línea)                             Dónde queda aquí
===========================================================  ==================
``mobility_card`` (``:11``, compute+store)                   columna (campos)
``driver_employee_id`` (``:12-18``, compute+store)           columna FK
                                                             ``driver_employee``
``driver_employee_name`` (``:19``, related)                  property
``future_driver_employee_id`` (``:20-25``, compute+store)    columna FK
``_compute_driver_employee_id`` (``:27-40``)                 método verbatim
``_compute_future_driver_employee_id`` (``:42-54``)          método verbatim
``_compute_mobility_card`` (``:56-64``)                      método verbatim
``_update_create_write_vals`` (``:66-102``)                  método verbatim
                                                             (dict) + receptor
                                                             ``pre_save``
``create`` (``:104-108``) / ``write`` (``:110-120``)         receptor
                                                             ``pre_save`` (ver
                                                             divergencia 1)
``action_open_employee`` (``:122-130``)                      NO portado
``open_assignation_logs`` (``:132-135``)                     NO portado
===========================================================  ==================

Lo que no se porta — y por qué
================================

- **``action_open_employee``** devuelve un ``ir.actions.act_window`` —
  navegación pura, sin equivalente DRF (mismo criterio que
  ``account_fleet/models/fleet_vehicle.py``, ``action_view_bills``). El
  dato es ``vehicle.driver_employee``.
- **``open_assignation_logs``** — doble razón, ambas medidas: (a) el método
  base NO existe en el ``fleet`` local (``grep -n "open_assignation_logs"
  addons/fleet/models/fleet_vehicle.py`` → 0; su punto 7 excluye los
  helpers ``ir.actions``), así que no hay ``super()`` que extender; (b) el
  override sólo sustituye la vista XML de la acción — capa de cliente.

Divergencias declaradas
=========================

1. **``create``/``write`` sobre ``vals`` → receptor ``pre_save``** — sin
   dict de valores, "qué lado cambió" se mide comparando contra el valor
   previo en BD; el método ``_update_create_write_vals`` se porta verbatim
   sobre un dict para el llamador que trabaje con ``vals`` (serializers), y
   el receptor aplica la misma regla de prioridad (el lado empleado gana,
   como el ``if/elif`` de la referencia) sobre la instancia.
2. **``index='btree_not_null'`` → índice del FK** — el índice parcial
   (sólo filas no nulas) de la referencia no se fabrica; el ``ForeignKey``
   de Django ya crea su B-tree completo (``db_index=True`` por defecto).
3. **``domain="['|', ('company_id', '=', False), …]"`` no se porta** — era
   filtro de UI del cliente; la coherencia de empresa la aplica el compute
   (agrupa por ``(work_contact, company)``, verbatim).
4. **``tracking=True`` no se porta** — el rastro de cambios del chatter es
   del cliente Odoo (mismo criterio que el ``fleet`` local, que tampoco lo
   porta en ``driver``).
5. **``sudo()`` → acceso directo** — sin usuario ambiente.
"""
import fields
import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from addons.fleet.models import FleetVehicle
from addons.hr.models.hr_employee import HrEmployee
from orm.model_classes import extend_model


def _employee_for_partner(partner_id, company_id):
    """El empleado cuyo contacto de trabajo es ``partner_id`` en la empresa
    ``company_id`` — el diccionario ``(partner, company) → employee`` que la
    referencia arma con ``_read_group``, resuelto fila a fila (este idioma
    no computa recordsets en lote)."""
    if not partner_id:
        return None
    return HrEmployee.objects.filter(
        work_contact_id=partner_id, company_id=company_id,
    ).first()


def _compute_driver_employee_id(self):
    """≙ ``_compute_driver_employee_id``
    (``odoo19c: hr_fleet/models/fleet_vehicle.py:27-40``)."""
    self.driver_employee = _employee_for_partner(self.driver_id, self.company_id)
    return self.driver_employee


def _compute_future_driver_employee_id(self):
    """≙ ``_compute_future_driver_employee_id`` (``:42-54``)."""
    self.future_driver_employee = _employee_for_partner(
        self.future_driver_id, self.company_id,
    )
    return self.future_driver_employee


def _compute_mobility_card(self):
    """≙ ``_compute_mobility_card`` (``:56-64``) — la tarjeta del empleado
    del conductor (por contacto de trabajo; si no, por usuario)."""
    employee = None
    if self.driver_id:
        employee = HrEmployee.objects.filter(
            work_contact_id=self.driver_id,
        ).first()
        if employee is None:
            employee = HrEmployee.objects.filter(
                resource__user__partner_id=self.driver_id,
            ).first()
    self.mobility_card = employee.mobility_card if employee else ''
    return self.mobility_card


def _update_create_write_vals(self, vals):
    """≙ ``_update_create_write_vals`` (``:66-102``) — verbatim sobre un
    dict de valores (claves locales, sin ``_id``): deriva el conductor
    partner del empleado, o el empleado del partner cuando es único (límite
    2, mismo truco de la referencia). Muta ``vals`` en el sitio."""
    if 'driver_employee' in vals:
        partner = None
        if vals['driver_employee']:
            employee = vals['driver_employee']
            if not isinstance(employee, HrEmployee):
                employee = HrEmployee.objects.get(pk=employee)
            partner = employee.work_contact
        vals['driver'] = partner
    elif 'driver' in vals:
        # El camino inverso, sólo si el empleado es único.
        employee = None
        if vals['driver']:
            employees = list(HrEmployee.objects.filter(
                work_contact=vals['driver'],
            )[:2])
            if len(employees) == 1:
                employee = employees[0]
        vals['driver_employee'] = employee

    # Lo mismo para el conductor futuro.
    if 'future_driver_employee' in vals:
        partner = None
        if vals['future_driver_employee']:
            employee = vals['future_driver_employee']
            if not isinstance(employee, HrEmployee):
                employee = HrEmployee.objects.get(pk=employee)
            partner = employee.work_contact
        vals['future_driver'] = partner
    elif 'future_driver' in vals:
        employee = None
        if vals['future_driver']:
            employees = list(HrEmployee.objects.filter(
                work_contact=vals['future_driver'],
            )[:2])
            if len(employees) == 1:
                employee = employees[0]
        vals['future_driver_employee'] = employee


def driver_employee_name(self):
    """≙ ``driver_employee_name`` (``related='driver_employee_id.name'``)."""
    return self.driver_employee.name if self.driver_employee_id else ''


@receiver(pre_save, sender=FleetVehicle,
          dispatch_uid='hr_fleet.vehicle_pre_save_sync_employee')
def _vehicle_pre_save(sender, instance, **kwargs):
    """El ``create``/``write`` de la referencia (``:104-120``), medido por
    diff contra BD (divergencia 1): sincroniza los pares
    conductor↔empleado, desuscribe al conductor saliente del chatter y
    refresca la tarjeta de movilidad (los tres computes almacenados)."""
    # ≙ "las claves están en vals": con ``update_fields`` acotado a columnas
    # ajenas al puente no hay nada que sincronizar (y un pre_save NO puede
    # ampliar ``update_fields`` — la señal lo recibe informativo, así que
    # sincronizar aquí no persistiría). El llamador que toque un lado del
    # par debe incluir ambos lados en su ``update_fields``.
    update_fields = kwargs.get('update_fields')
    synced_fields = {'driver', 'driver_employee', 'future_driver',
                     'future_driver_employee', 'mobility_card'}
    if update_fields is not None and not (set(update_fields) & synced_fields):
        return

    old = {}
    if instance.pk is not None:
        old = (FleetVehicle.objects.filter(pk=instance.pk)
               .values('driver_id', 'driver_employee_id',
                       'future_driver_employee_id', 'future_driver_id')
               .first()) or {}

    # ≙ la rama del ``write`` que desuscribe al conductor saliente
    # (``:110-120``) — con los valores VIEJOS, como la referencia.
    old_driver_employee_id = old.get('driver_employee_id')
    if (old_driver_employee_id
            and instance.driver_employee_id != old_driver_employee_id):
        partners_to_unsubscribe = []
        if old.get('driver_id'):
            partners_to_unsubscribe.append(old['driver_id'])
        old_employee = HrEmployee.objects.filter(
            pk=old_driver_employee_id,
        ).first()
        if old_employee is not None and old_employee.user is not None:
            partners_to_unsubscribe.append(old_employee.user.partner_id)
        if partners_to_unsubscribe:
            instance.message_unsubscribe(partners_to_unsubscribe)

    # ≙ ``_update_create_write_vals`` aplicado a la instancia: gana el lado
    # que cambió; con empate, el lado empleado (el ``if`` antes del
    # ``elif``, verbatim).
    def _sync_pair(employee_attr, partner_attr):
        employee_id = getattr(instance, f'{employee_attr}_id')
        partner_id = getattr(instance, f'{partner_attr}_id')
        if employee_id != old.get(f'{employee_attr}_id'):
            employee = getattr(instance, employee_attr)
            setattr(instance, partner_attr,
                    employee.work_contact if employee else None)
        elif partner_id != old.get(f'{partner_attr}_id'):
            employee = None
            if partner_id:
                employees = list(HrEmployee.objects.filter(
                    work_contact_id=partner_id,
                )[:2])
                if len(employees) == 1:
                    employee = employees[0]
            setattr(instance, employee_attr, employee)

    _sync_pair('driver_employee', 'driver')
    _sync_pair('future_driver_employee', 'future_driver')
    instance._compute_mobility_card()


def apply_hr_fleet_fleet_vehicle_extensions():
    """Cuelga sobre ``fleet.vehicle`` lo que ``hr_fleet`` necesita —
    ≙ ``_inherit``. Se invoca desde ``HrFleetConfig.ready()``. Las tres
    columnas nuevas esperan su migración en ``fleet/migrations/`` (ver
    ``__init__.py`` del addon)."""
    extend_model(
        'fleet', 'FleetVehicle',
        campos={
            'mobility_card': fields.Char(
                max_length=64, blank=True, default='',
                verbose_name='Tarjeta de movilidad',
                help_text='Odoo mobility_card (compute+store — lo refresca '
                          'el receptor pre_save de hr_fleet).',
            ),
            'driver_employee': fields.Many2one(
                'hr.HrEmployee', on_delete=models.SET_NULL, null=True,
                blank=True, related_name='car_ids',
                verbose_name='Driver (Employee)',
                help_text='Odoo driver_employee_id (compute+store; su índice '
                          'btree_not_null no se fabrica — divergencia 2). El '
                          'related_name conserva el nombre del One2many '
                          'car_ids de la referencia (hr_fleet/employee.py).',
            ),
            'future_driver_employee': fields.Many2one(
                'hr.HrEmployee', on_delete=models.SET_NULL, null=True,
                blank=True, related_name='future_car_ids',
                verbose_name='Future Driver (Employee)',
                help_text='Odoo future_driver_employee_id (compute+store).',
            ),
        },
        metodos={
            '_compute_driver_employee_id': _compute_driver_employee_id,
            '_compute_future_driver_employee_id': _compute_future_driver_employee_id,
            '_compute_mobility_card': _compute_mobility_card,
            '_update_create_write_vals': _update_create_write_vals,
        },
        propiedades={
            'driver_employee_name': driver_employee_name,
        },
    )
