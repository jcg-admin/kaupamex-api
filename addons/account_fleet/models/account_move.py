r"""``account.move`` / ``account.move.line`` — vínculo con vehículos.

Adaptación de Odoo ``account_fleet/models/account_move.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte completo — 8 símbolos de la referencia, cita por cita
=============================================================

``odoo19c: addons/account_fleet/models/account_move.py`` (61 líneas, ``wc
-l``): 1
método sobre ``AccountMove`` y 3 campos + 4 métodos sobre ``AccountMoveLine``.
Los 8 están aquí:

===================================  ===========================================
Símbolo de la referencia (línea)     Dónde queda en este puerto
===================================  ===========================================
``AccountMove._post`` (9-29)         receptor ``post_save`` (ver "Por qué señal, no override")
``AccountMoveLine.vehicle_id`` (35)  campo ``vehicle`` (``add_to_class``)
``AccountMoveLine.need_vehicle`` (37) campo ``NonStored`` (compute ``_compute_need_vehicle``)
``vehicle_log_service_ids`` (38-39)  accesor inverso de ``fleet.FleetVehicleLogServices.account_move_line`` (``related_name='vehicle_log_services'``) — ver ``fleet_vehicle_log_services.py``
``_compute_need_vehicle`` (41-42)    método homónimo
``_prepare_fleet_log_service`` (44-52) método homónimo
``AccountMoveLine.write`` (54-57)    receptor ``post_save`` (ver "Por qué señal, no override")
``AccountMoveLine.unlink`` (59-61)   receptor ``pre_delete`` (ver "Por qué señal, no override")
===================================  ===========================================

Ningún símbolo se omite.

Por qué señal, no override — mismo patrón que ``l10n_mx``
=============================================================

La referencia sobreescribe ``_post``/``write``/``unlink`` con ``super()``
real, vía ``_inherit``. Django no admite reabrir la clase de otro app para
insertar un método en su cadena de resolución sin monkeypatchear la propia
definición — y el gate de este proyecto ya fijó, para el mismo problema en
``l10n_mx/models/account_move_line.py`` (``_compute_account_id`` sin base que
extender) y en ``stock/handlers.py::_cache_return_old_status``, que el punto
de enganche correcto es una **señal de Django** conectada desde
``apply_account_fleet_extensions()``: se dispara en el mismo momento del
ciclo de vida (guardado/borrado), sin necesitar reescribir el método ajeno.

- ``_post`` → ``post_save`` sobre ``AccountMove``, filtrando por
  ``update_fields`` que incluya ``'state'`` y ``instance.state == 'posted'``
  — el mismo momento en que ``account.post()`` (``api:
  account/models/account_move.py:246``) hace su propio
  ``save(update_fields=[..., 'state', ...])``. Detecta "se acaba de postear"
  sin necesitar interceptar la llamada al método.
- ``write`` (sólo la rama que vacía ``vehicle_id``) → ``post_save`` sobre
  ``AccountMoveLine``, mismo criterio de ``update_fields``.
- ``unlink`` → ``pre_delete`` sobre ``AccountMoveLine``: limpia los servicios
  vinculados ANTES de que la línea se borre (Django dispara ``pre_delete``
  antes del ``DELETE``, momento equivalente al ``unlink()`` de la
  referencia, que limpia antes de invocar ``super().unlink()``).

Divergencias declaradas
=========================

1. **``vendor_id`` → ``move.partner``, no ``line.partner``.** La referencia
   lee ``self.partner_id`` de la LÍNEA (``account.move.line.partner_id``,
   campo related/stored en Odoo). ``api: account/models/account_move_line.py``
   no declara ``partner`` — medido: ``grep -n "partner" account_move_line.py``
   → 0 hits. Se navega al partner del ASIENTO
   (``self.move.partner``), que es lo que la línea de la referencia también
   termina resolviendo cuando su propio ``partner_id`` no fue sobreescrito a
   mano (caso normal de una factura de proveedor sin partner por línea).
2. **``_get_html_link()`` → ``str(move)``.** La referencia arma un enlace
   HTML clickeable para el mensaje del chatter
   (``move_id._get_html_link()``); este stack es headless (DRF, sin motor de
   render HTML de registros). Se usa la representación textual
   (``AccountMove.__str__``, ``api: account_move.py:139``) — mismo dato
   (el número del asiento), sin el `<a href>`.
3. **``ignore_linked_bill_constraint`` — ``with_context`` → ``contextvars``.**
   La referencia propaga el flag con ``self.sudo().vehicle_log_service_ids.
   with_context(ignore_linked_bill_constraint=True).unlink()`` — el contexto
   ambiente de Odoo. Este stack no tiene contexto de request en el modelo
   (mismo hueco que ``res_company.py`` documenta para ``self.env.user``); el
   equivalente construido aquí es un ``contextvars.ContextVar`` de módulo
   (API pública de Python, no una invención del proyecto), expuesto como el
   context manager ``ignore_linked_bill_constraint()`` — ver
   ``fleet_vehicle_log_services.py``, que es quien lo declara (protege SU
   propio guard de borrado).
4. **``self.sudo()`` no tiene análogo.** No hay modelo de permisos a nivel de
   ORM en este stack (la autorización vive en la capa DRF, ``HasCapability``
   — ``api: CLAUDE.md``); el borrado de limpieza no necesita elevar
   privilegios porque no hay ACL de fila que sortear aquí.
"""
import fields
import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from addons.account.models import AccountMove, AccountMoveLine
from addons.account_fleet.models.fleet_vehicle_log_services import (
    ignore_linked_bill_constraint,
)
from addons.base.models import IrModelData
from addons.fleet.models import FleetVehicleLogServices
from tools.translate import _

#: Identificador externo del tipo de servicio semilla — ≙
#: ``account_fleet.data_fleet_service_type_vendor_bill``
#: (``data/fleet_service_type_data.xml``). Se siembra en
#: ``migrations/0001_seed_fleet_service_type_vendor_bill.py``.
VENDOR_BILL_SERVICE_XMLID = 'account_fleet.data_fleet_service_type_vendor_bill'


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya.

    Idéntico al de ``account``/``l10n_mx``/``account_qr_code_emv``:
    ``ready()`` puede correr más de una vez en tests que recargan el
    registro de apps.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


# -- las funciones que se cuelgan por nombre en apply_account_fleet_extensions() --


def _compute_need_vehicle(self):
    """≙ ``_compute_need_vehicle`` (``odoo19c: account_move.py:41-42``).

    Constante ``False`` en el puerto base: el campo existe para que un
    addon de UI decida cuándo hacer editable ``vehicle`` en el formulario de
    la línea — sin capa de formularios, la decisión la toma el cliente.
    """
    return False


def _prepare_fleet_log_service(self):
    """≙ ``_prepare_fleet_log_service`` (``odoo19c: account_move.py:44-52``).

    Los valores para crear el ``fleet.vehicle.log.services`` que esta línea
    de factura de proveedor origina. Ver divergencia 1 (``vendor`` desde el
    asiento, no la línea).
    """
    vendor_bill_service = IrModelData.ref(
        VENDOR_BILL_SERVICE_XMLID, raise_if_not_found=False)
    return {
        'service_type': vendor_bill_service,
        'vehicle': self.vehicle,
        'vendor': self.move.partner,
        'description': self.name,
        'account_move_line': self,
    }


@receiver(post_save, sender=AccountMove,
          dispatch_uid='account_fleet.create_service_bills_on_post')
def _create_fleet_service_bills_on_post(sender, instance, update_fields, **kwargs):
    """≙ ``AccountMove._post`` (``odoo19c: account_move.py:9-29``).

    Crea un ``fleet.vehicle.log.services`` por cada línea de producto con
    vehículo de una factura de proveedor (``move_type == 'in_invoice'``) que
    se acaba de postear. Idempotente: una línea que ya tiene su servicio
    vinculado (``vehicle_log_services`` no vacío) se salta — mismo guard que
    la referencia (``line.vehicle_log_service_ids``).
    """
    if not update_fields or 'state' not in update_fields:
        return
    if instance.state != 'posted':
        return
    if instance.move_type != 'in_invoice':
        return
    vendor_bill_service = IrModelData.ref(
        VENDOR_BILL_SERVICE_XMLID, raise_if_not_found=False)
    if vendor_bill_service is None:
        # ≙ "if not vendor_bill_service: return super()._post(soft)" — sin
        # el tipo semilla, el posteo sigue su curso normal (ya ocurrió: esta
        # señal corre EN post_save, después del guardado) y no se crea nada.
        return
    for line in instance.line_ids.all():
        if line.vehicle is None:
            continue
        if line.display_type != 'product':
            continue
        if FleetVehicleLogServices.objects.filter(account_move_line=line).exists():
            continue
        vals = line._prepare_fleet_log_service()
        log_service = FleetVehicleLogServices.objects.create(**vals)
        log_service.message_post(body=_(
            'Servicio de factura de proveedor: %(move)s'
        ) % {'move': str(instance)})


@receiver(post_save, sender=AccountMoveLine,
          dispatch_uid='account_fleet.detach_services_on_vehicle_cleared')
def _detach_vehicle_services_on_line_saved(sender, instance, created, update_fields,
                                            **kwargs):
    """≙ la rama de ``AccountMoveLine.write`` que vacía ``vehicle_id``
    (``odoo19c: account_move.py:54-57``).

    Sólo actúa en un guardado completo (``update_fields`` ``None``) o uno que
    explícitamente toca ``vehicle`` — un ``save(update_fields=['debit'])``
    no dispara esta limpieza, igual que un ``write({'debit': ...})`` de la
    referencia no toca ``vehicle_id``.
    """
    if created:
        return
    if update_fields is not None and 'vehicle' not in update_fields:
        return
    if instance.vehicle is not None:
        return
    with ignore_linked_bill_constraint():
        FleetVehicleLogServices.objects.filter(account_move_line=instance).delete()


@receiver(pre_delete, sender=AccountMoveLine,
          dispatch_uid='account_fleet.detach_services_before_line_deleted')
def _detach_vehicle_services_before_line_deleted(sender, instance, **kwargs):
    """≙ ``AccountMoveLine.unlink`` (``odoo19c: account_move.py:59-61``)."""
    with ignore_linked_bill_constraint():
        FleetVehicleLogServices.objects.filter(account_move_line=instance).delete()


def apply_account_fleet_extensions():
    """Cuelga sobre ``account.move``/``account.move.line`` lo que
    ``account_fleet`` necesita — ≙ ``_inherit``.

    Se invoca desde ``AccountFleetConfig.ready()``: en tiempo de import el
    registro de modelos aún no está poblado. Los receptores ``@receiver`` de
    arriba se conectan al importar este módulo (no hace falta conectarlos
    aquí) — el propio ``importlib.import_module`` de ``ready()`` ya ejecuta
    el cuerpo del módulo una vez.
    """
    # --- account.move.line (2 de 3 campos; el tercero es un accesor inverso) ---
    _add_if_absent(
        AccountMoveLine, 'vehicle',
        fields.Many2one(
            'fleet.FleetVehicle', on_delete=models.SET_NULL, null=True,
            blank=True, related_name='account_move_lines', db_index=True,
            help_text='Vehículo asociado a este apunte (Odoo vehicle_id). '
                      'Al postear una factura de proveedor con este campo '
                      'seteado en una línea de producto, se crea el '
                      'servicio de flota correspondiente.'),
    )
    if not hasattr(AccountMoveLine, 'need_vehicle'):
        AccountMoveLine.add_to_class('need_vehicle', fields.NonStored(
            default=_compute_need_vehicle,
            help_text='Si el apunte admite asociar un vehículo (Odoo '
                      'need_vehicle, compute, store=False). Constante False '
                      'en el puerto base — un addon de UI lo redefine.',
        ))
    # ``vehicle_log_service_ids`` (Odoo) no se agrega aquí — es el accesor
    # inverso de ``FleetVehicleLogServices.account_move_line``
    # (``related_name='vehicle_log_services'``), que ``fleet_vehicle_log_
    # services.py`` declara. ``line.vehicle_log_services.all()`` es el
    # equivalente de ``line.vehicle_log_service_ids``.

    # --- métodos (no son campos: se cuelgan directo) ------------------------
    for modelo, metodos in (
        (AccountMoveLine, {
            '_compute_need_vehicle': _compute_need_vehicle,
            '_prepare_fleet_log_service': _prepare_fleet_log_service,
        }),
    ):
        for nombre, funcion in metodos.items():
            if not hasattr(modelo, nombre):
                setattr(modelo, nombre, funcion)
