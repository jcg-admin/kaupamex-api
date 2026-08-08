r"""``fleet.vehicle.log.services`` — vínculo con la línea de factura que lo originó.

Adaptación de Odoo ``account_fleet/models/fleet_vehicle_log_services.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte completo — 9 símbolos de la referencia, cita por cita
=============================================================

``odoo19c: addons/account_fleet/models/fleet_vehicle_log_services.py`` (50
líneas, ``wc -l``): 4 campos + 5 métodos. Los 9 están aquí:

===================================  ===========================================
Símbolo de la referencia (línea)     Dónde queda en este puerto
===================================  ===========================================
``account_move_line_id`` (10)        campo ``account_move_line`` (``add_to_class``, ``unique=True``)
``account_move_state`` (11)          property ``account_move_state``
``amount`` (12-13, REDEFINIDO)       ``sync_amount_from_line`` + guard ``pre_save`` (ver "amount/vehicle")
``vehicle_id`` (14-15, REDEFINIDO)   ``sync_vehicle_from_line`` (ver "amount/vehicle")
``_compute_vehicle_id`` (17-22)      método homónimo == ``sync_vehicle_from_line``
``_inverse_amount`` (25-27)          receptor ``pre_save`` (guard, ver "amount/vehicle")
``_compute_amount`` (29-32)          método homónimo == ``sync_amount_from_line``
``action_open_account_move`` (34-42) método ``get_account_move`` (ver divergencia 1)
``_unlink_if_no_linked_bill`` (45-51) receptor ``pre_delete`` (guard)
===================================  ===========================================

Ningún símbolo se omite.

``amount``/``vehicle`` — cómo se porta un campo REDEFINIDO sin poder tocar
``fleet/models/fleet_vehicle_log_services.py``
=================================================================================

Ambos campos **ya existen** en ``fleet.FleetVehicleLogServices``
(``api: addons/fleet/models/fleet_vehicle_log_services.py:32,34-35``) — este
addon no los agrega (``_add_if_absent`` los deja intactos), sólo cambia su
**comportamiento**: la referencia los redeclara con
``compute=...``/``inverse=...``/``store=True`` (Odoo permite reabrir un campo
ajeno con ``_inherit``; este ORM no). El equivalente construido:

- **``vehicle`` (≙ ``_compute_vehicle_id``)** — ``sync_vehicle_from_line``
  se llama (a) al crear el servicio con ``account_move_line`` ya seteado
  (``post_save`` de este propio modelo, ``created=True``), y (b) cuando la
  línea vinculada cambia (``post_save`` de ``AccountMoveLine``, resolviendo
  el servicio vía el accesor inverso). Sin ``inverse=``, la referencia deja
  editable el campo a mano — este puerto también: no hay guard sobre
  ``vehicle``.
- **``amount`` (≙ ``_compute_amount`` + ``_inverse_amount``)** — mismo
  disparador de sincronización, PERO con guard: la referencia declara
  ``inverse='_inverse_amount'``, que en Odoo intercepta cualquier escritura
  manual del usuario (en vez de guardar el valor, corre el inverso). Aquí el
  guard es un receptor ``pre_save`` (``_guard_amount_immutable_when_billed``)
  que RECHAZA el guardado si ``amount`` cambia y el servicio está vinculado a
  una línea — salvo que el guardado venga de la propia sincronización
  (bypass con el ``contextvars.ContextVar`` ``_SYNCING_FROM_BILL``, mismo
  mecanismo y misma razón que ``ignore_linked_bill_constraint`` de este
  archivo — ver el punto 2 de abajo).

Divergencias declaradas
=========================

1. **``action_open_account_move`` → ``get_account_move()`` sin
   ``ir.actions``.** La referencia devuelve un diccionario de acción para que
   el cliente de Odoo abra el formulario del asiento
   (``odoo19c: fleet_vehicle_log_services.py:34-42``). Sin capa de vistas en
   este stack (mismo criterio que ``fleet_vehicle.py::action_view_bills``,
   pero éste SÍ se porta): la referencia resuelve **qué registro abrir**
   (``self.account_move_line_id.move_id``) — esa resolución sí tiene
   equivalente y es lo que se porta; lo que no tiene equivalente es el
   ``dict`` de navegación del cliente Odoo. Se devuelve el propio
   ``account.move``, para que quien construya la ruta del frontend (fuera de
   este addon, sin capa DRF todavía) la arme con el id.
2. **``ignore_linked_bill_constraint`` vive aquí, no en ``account_move.py``.**
   El guard que protege (``_unlink_if_no_linked_bill``) es de ESTE modelo, así
   que el context manager que lo desactiva se declara junto a él —
   ``account_move.py`` lo importa para envolver su propia limpieza de
   ``write``/``unlink`` (ver ese módulo, divergencia 3).
"""
import contextlib
import contextvars

import fields
import models
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from addons.account.models import AccountMoveLine
from addons.fleet.models import FleetVehicleLogServices
from exceptions import UserError
from tools.translate import _

#: Bypass del guard de ``amount`` (≙ ``_inverse_amount``) durante la propia
#: sincronización — mismo criterio que ``ignore_linked_bill_constraint`` de
#: abajo: un ``contextvars.ContextVar`` de módulo, API pública de Python, no
#: una invención del proyecto. Ver el docstring del módulo.
_SYNCING_FROM_BILL = contextvars.ContextVar(
    'account_fleet_syncing_from_bill', default=False)

#: Bypass del guard de borrado (≙ ``_unlink_if_no_linked_bill``) — la
#: referencia lo propaga con ``with_context(ignore_linked_bill_constraint=
#: True)``; aquí, el mismo mecanismo que ``_SYNCING_FROM_BILL``.
_IGNORE_LINKED_BILL_CONSTRAINT = contextvars.ContextVar(
    'account_fleet_ignore_linked_bill_constraint', default=False)


@contextlib.contextmanager
def ignore_linked_bill_constraint():
    """≙ ``with_context(ignore_linked_bill_constraint=True)`` de la
    referencia — ver ``_unlink_if_no_linked_bill`` y ``account_move.py``
    (que lo usa para su propia limpieza de ``write``/``unlink``)."""
    token = _IGNORE_LINKED_BILL_CONSTRAINT.set(True)
    try:
        yield
    finally:
        _IGNORE_LINKED_BILL_CONSTRAINT.reset(token)


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya.

    Idéntico al de ``account``/``l10n_mx``/``account_qr_code_emv``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


# -- las funciones que se cuelgan por nombre en apply_account_fleet_extensions() --


def account_move_state(self):
    """≙ ``account_move_state`` (``odoo19c: fleet_vehicle_log_services.py:11``).

    ``related='account_move_line_id.parent_state'`` en la referencia;
    ``parent_state`` es a su vez un ``related='move_id.state'`` de
    ``account.move.line`` que este puerto no declara (medido: ``grep -n
    "parent_state" api: src/addons/account/models/account_move_line.py`` →
    0 hits) — se navega directo a ``account_move_line.move.state``.
    """
    line = self.account_move_line
    return line.move.state if line is not None else None


def get_account_move(self):
    """≙ ``action_open_account_move`` (``odoo19c: fleet_vehicle_log_services.py:34-42``).

    Ver divergencia 1 del docstring del módulo: devuelve el ``account.move``
    a abrir en vez de un diccionario de navegación de Odoo.
    """
    line = self.account_move_line
    return line.move if line is not None else None


def sync_vehicle_from_line(self):
    """≙ ``_compute_vehicle_id`` (``odoo19c: fleet_vehicle_log_services.py:17-22``).

    Sólo pisa ``vehicle`` si la línea vinculada trae uno propio — la
    referencia evita vaciar un campo requerido cuando la línea no lo tiene
    (comentario original: *"We avoid emptying the vehicle_id as it is a
    required field"*).
    """
    line = self.account_move_line
    if line is None:
        return
    line_vehicle = line.vehicle
    if line_vehicle is None:
        return
    self.vehicle = line_vehicle


def sync_amount_from_line(self):
    """≙ ``_compute_amount`` (``odoo19c: fleet_vehicle_log_services.py:29-32``).

    El costo del servicio es el debe (``debit``) de la línea vinculada.
    """
    line = self.account_move_line
    if line is None:
        return
    self.amount = line.debit


def _sync_service_fields_from_line(service):
    """El punto único que sincroniza ``vehicle``/``amount`` — usado tanto al
    crear el servicio como al cambiar la línea vinculada. Bypassa el guard
    de ``amount`` con ``_SYNCING_FROM_BILL``: es el propio compute, no una
    escritura manual del usuario."""
    if service.account_move_line is None:
        return
    sync_vehicle_from_line(service)
    sync_amount_from_line(service)
    token = _SYNCING_FROM_BILL.set(True)
    try:
        service.save(update_fields=['vehicle', 'amount'])
    finally:
        _SYNCING_FROM_BILL.reset(token)


@receiver(post_save, sender=FleetVehicleLogServices,
          dispatch_uid='account_fleet.sync_service_fields_on_create')
def _sync_service_fields_on_create(sender, instance, created, **kwargs):
    """Dispara la sincronización inicial cuando el servicio nace ya
    vinculado a una línea (caso normal: lo crea
    ``account_move.py::_create_fleet_service_bills_on_post``)."""
    if not created:
        return
    _sync_service_fields_from_line(instance)


@receiver(post_save, sender=AccountMoveLine,
          dispatch_uid='account_fleet.resync_service_fields_on_line_change')
def _resync_service_fields_on_line_change(sender, instance, created, **kwargs):
    """≙ los ``@api.depends`` de ``_compute_vehicle_id``/``_compute_amount``
    reaccionando a un cambio en la línea vinculada (no en su creación, que
    ya cubre el receptor de arriba)."""
    if created:
        return
    service = FleetVehicleLogServices.objects.filter(
        account_move_line=instance).first()
    if service is not None:
        _sync_service_fields_from_line(service)


@receiver(pre_save, sender=FleetVehicleLogServices,
          dispatch_uid='account_fleet.guard_amount_immutable_when_billed')
def _guard_amount_immutable_when_billed(sender, instance, **kwargs):
    """≙ ``_inverse_amount`` (``odoo19c: fleet_vehicle_log_services.py:25-27``).

    Un servicio vinculado a una línea de factura no admite editar ``amount``
    a mano — se recalcula desde la línea. El bypass (``_SYNCING_FROM_BILL``)
    es lo que distingue "esto lo escribió el propio compute" de "esto lo
    escribió el llamador"; sin él, ``_sync_service_fields_from_line`` se
    bloquearía a sí misma.
    """
    if instance.account_move_line is None:
        return
    if _SYNCING_FROM_BILL.get():
        return
    if instance.pk is None:
        # Creación con account_move_line ya seteado a mano (fuera del flujo
        # normal de ``account_move.py``): el compute todavía no corrió — se
        # deja pasar el guardado inicial; el post_save de creación
        # sincroniza y sella el valor correcto justo después.
        return
    previo = type(instance).objects.filter(pk=instance.pk).values_list(
        'amount', flat=True).first()
    if previo is not None and previo != instance.amount:
        raise UserError(_(
            'No se puede modificar el costo de un servicio vinculado a una '
            'línea de factura. Edítalo en el asiento contable relacionado.'))


@receiver(pre_delete, sender=FleetVehicleLogServices,
          dispatch_uid='account_fleet.unlink_if_no_linked_bill')
def _unlink_if_no_linked_bill(sender, instance, **kwargs):
    """≙ ``_unlink_if_no_linked_bill`` (``odoo19c:
    fleet_vehicle_log_services.py:45-51``, ``@api.ondelete(at_uninstall=
    False)``)."""
    if instance.account_move_line is None:
        return
    if _IGNORE_LINKED_BILL_CONSTRAINT.get():
        return
    raise UserError(_(
        'No se puede eliminar un servicio de flota creado desde una '
        'factura de proveedor.'))


def apply_account_fleet_extensions():
    """Cuelga sobre ``fleet.vehicle.log.services`` lo que ``account_fleet``
    necesita — ≙ ``_inherit``. Se invoca desde
    ``AccountFleetConfig.ready()``.

    Los receptores ``@receiver`` de arriba se conectan al importar este
    módulo — no hace falta conectarlos aquí.
    """
    _add_if_absent(
        FleetVehicleLogServices, 'account_move_line',
        fields.Many2one(
            'account.AccountMoveLine', on_delete=models.SET_NULL, null=True,
            blank=True, unique=True, related_name='vehicle_log_services',
            help_text='Línea de factura de proveedor que originó este '
                      'servicio (Odoo account_move_line_id, one2one). '
                      '``unique=True`` porque una línea genera a lo sumo un '
                      'servicio (idempotencia verificada antes de crear).'),
    )
    for nombre, funcion in (
        ('account_move_state', property(account_move_state)),
        ('get_account_move', get_account_move),
        ('sync_vehicle_from_line', sync_vehicle_from_line),
        ('sync_amount_from_line', sync_amount_from_line),
        ('_compute_vehicle_id', sync_vehicle_from_line),
        ('_compute_amount', sync_amount_from_line),
    ):
        if not hasattr(FleetVehicleLogServices, nombre):
            setattr(FleetVehicleLogServices, nombre, funcion)
