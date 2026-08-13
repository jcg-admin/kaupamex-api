r"""``fleet.vehicle`` — facturas de proveedor asociadas al vehículo.

Adaptación de Odoo ``account_fleet/models/fleet_vehicle.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte — 4 símbolos de la referencia, cita por cita
=====================================================

``odoo19c: addons/account_fleet/models/fleet_vehicle.py`` (44 líneas, ``wc
-l``): 2
campos + 2 métodos sobre ``FleetVehicle``:

===================================  ===========================================
Símbolo de la referencia (línea)     Dónde queda en este puerto
===================================  ===========================================
``bill_count`` (10)                  property ``bill_count``
``account_move_ids`` (11)            property ``account_move_ids``
``_compute_move_ids`` (13-31)        método homónimo (calcula ambos a la vez)
``action_view_bills`` (33-44)        DEFERIDO — ver "Lo que no se porta"
===================================  ===========================================

3 de 4 portados; 1 deferido con razón medida (no silenciado).

Lo que no se porta — y por qué
================================

**``action_view_bills`` es navegación pura.** Devuelve un diccionario
``ir.actions.act_window`` (``result = self.env['ir.actions.act_window']._for_
xml_id(...)``) para que el cliente de Odoo abra una vista de lista/formulario
con las facturas del vehículo. No hay ``ir.actions`` en este stack (DRF,
headless) ni una vista que dibujar — mismo criterio que la propia ``fleet``
ya declara para sus pares (``fleet/models/fleet_vehicle.py``, punto 7 de su
docstring: *"NO se portan los helpers de navegación de vista ... que
devuelven diccionarios ir.actions.act_window, sin equivalente DRF"*). No es
un recorte nuevo: es la misma exclusión, aplicada al mismo tipo de símbolo.

Lo que SÍ hace falta para portar los otros 3 — y no existía
===============================================================

``self.env['account.move'].get_purchase_types()`` — medido: ``grep -rn
"get_purchase_types" api: src/addons/account/models/account_move.py`` → **0
hits**. La referencia usa este método para acotar las líneas a facturas/notas
de crédito/recibos de COMPRA (``odoo19c: account_move.py:6488-6492`` →
``('in_invoice', 'in_refund', 'in_receipt')``, verbatim el mismo conjunto que
``AccountMove.MOVE_TYPES`` de este puerto ya declara con esos tres códigos).
Se declara aquí como constante local (``PURCHASE_MOVE_TYPES``) en vez de
tocar ``account/models/account_move.py`` (fuera de alcance de este agente).

Divergencias declaradas
=========================

1. **Sin gate de grupo (``account.group_account_readonly``).** La referencia
   vacía ambos campos si el usuario no tiene ese grupo
   (``odoo19c: fleet_vehicle.py:14-17``). Este stack no tiene usuario
   ambiente en la capa de modelo (mismo hueco que ``res_company.py``
   documenta para ``self.env.user`` — "el usuario se recibe explícito, no
   ambiente"). La propiedad siempre calcula sobre datos completos; el
   gate de autorización (DEC-11, ``HasCapability``) es responsabilidad de la
   vista DRF que exponga estos campos — no existe todavía (fuera de alcance:
   este addon no declara capa DRF, sólo modelos).
2. **``parent_state != 'cancel'`` → ``move__state__in=('draft', 'posted')``.**
   Equivalente exacto sobre el conjunto de 3 estados de
   ``AccountMove.STATES`` — no hay tercer valor que excluir aparte de
   ``'cancel'``.
"""
from addons.account.models import AccountMove, AccountMoveLine
from addons.fleet.models import FleetVehicle

#: ≙ ``AccountMove.get_purchase_types()`` de la referencia (ausente en este
#: puerto — ver docstring del módulo). Mismo conjunto verbatim.
PURCHASE_MOVE_TYPES = ('in_invoice', 'in_refund', 'in_receipt')


def _get_vehicle_bill_lines(self):
    """Líneas de apunte con ``vehicle == self``, de facturas de compra no
    canceladas — el ``domain`` de ``_compute_move_ids``
    (``odoo19c: fleet_vehicle.py:19-24``)."""
    return AccountMoveLine.objects.filter(
        vehicle=self,
        move__state__in=('draft', 'posted'),
        move__move_type__in=PURCHASE_MOVE_TYPES,
    )


def _compute_move_ids(self):
    """≙ ``_compute_move_ids`` (``odoo19c: fleet_vehicle.py:13-31``).

    Devuelve ambos valores a la vez (``account_move_ids`` y ``bill_count``)
    en un único recorrido — las properties individuales de abajo llaman a
    esta misma función cuando se piden por separado; se expone también
    suelta para el llamador que quiera las dos cosas en una sola consulta.
    """
    lines = _get_vehicle_bill_lines(self)
    move_pks = lines.values_list('move', flat=True).distinct()
    moves = AccountMove.objects.filter(pk__in=move_pks)
    return {'account_move_ids': moves, 'bill_count': moves.count()}


def account_move_ids(self):
    """≙ ``account_move_ids`` (``odoo19c: fleet_vehicle.py:11``) — las
    facturas de compra que citan este vehículo en alguna línea."""
    return _compute_move_ids(self)['account_move_ids']


def bill_count(self):
    """≙ ``bill_count`` (``odoo19c: fleet_vehicle.py:10``)."""
    return _compute_move_ids(self)['bill_count']


def apply_account_fleet_extensions():
    """Cuelga sobre ``fleet.vehicle`` lo que ``account_fleet`` necesita —
    ≙ ``_inherit``. Se invoca desde ``AccountFleetConfig.ready()``.

    Ninguno de los dos campos tiene columna (ambos son ``compute`` sin
    ``store=True`` en la referencia): se cuelgan como ``property``, no via
    ``add_to_class`` — no hay migración pendiente para este archivo.
    """
    for nombre, funcion in (
        ('account_move_ids', account_move_ids),
        ('bill_count', bill_count),
    ):
        if not hasattr(FleetVehicle, nombre):
            setattr(FleetVehicle, nombre, property(funcion))
    if not hasattr(FleetVehicle, '_compute_move_ids'):
        setattr(FleetVehicle, '_compute_move_ids', _compute_move_ids)
