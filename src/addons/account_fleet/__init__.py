"""``account_fleet`` — puente Contabilidad ↔ Flota (Odoo ``account_fleet``).

Adaptación de Odoo ``account_fleet`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: un módulo puente ("bridge" — su ``__manifest__.py`` lo declara
``auto_install: True`` cuando ``fleet`` y ``account`` están ambos instalados)
que NO declara modelos propios: cuelga vocabulario cruzado sobre los cuatro
modelos que ya existen en ``account``/``fleet`` — ``account.move``,
``account.move.line``, ``fleet.vehicle``, ``fleet.vehicle.log.services`` — y
sobre un quinto, ``account.automatic.entry.wizard``, que no existe todavía en
este puerto (ver ``wizard/account_automatic_entry_wizard.py``).

Al postear una factura de proveedor con líneas de producto marcadas con un
vehículo, este addon crea automáticamente el servicio de flota
correspondiente («Vendor Bill») y lo vincula a la línea que lo originó —
igual que la referencia, con el mismo tipo de servicio semilla
(``data/fleet_service_types.py``).

Mecanismo — ``add_to_class``/``setattr`` desde ``ready()``, igual que
``account`` (sobre ``product``/``res.company``/``res.currency``),
``l10n_mx`` y ``account_qr_code_emv``/``account_qr_code_sepa`` (sobre
``res.partner.bank``): es el patrón ya establecido en este árbol para un
``_inherit`` cruzado de addon, y el que este archivo sigue.

Wiring pendiente (mismo patrón que ``account_qr_code_emv``, divergencia 4 de
ese módulo): este agente tiene prohibido escribir fuera de
``account_fleet/`` y sus tests. Quedan para el orquestador:

1. Añadir ``'addons.account_fleet'`` a ``INSTALLED_APPS``
   (``config/settings/base.py``) — sin esto, ``AccountFleetConfig.ready()``
   no se dispara solo (los tests de este addon llaman
   ``apply_account_fleet_extensions()`` explícitamente, ver cada módulo).
2. Las migraciones que agregan las columnas nuevas — ``vehicle`` en
   ``account.AccountMoveLine`` y ``account_move_line`` en
   ``fleet.FleetVehicleLogServices`` — deben vivir en ``account/migrations/``
   y ``fleet/migrations/`` respectivamente (Django exige que la migración de
   una columna viva en la app dueña del modelo; mismo criterio que
   ``base/migrations/0015_resbank_l10n_mx_edi_code_and_more.py`` para los
   campos que ``l10n_mx`` cuelga sobre ``res.partner.bank``). Sin ellas, el
   campo existe en el registro de Django (``add_to_class`` ya lo declaró) pero
   no en la base — cualquier ``.save()``/``.objects.create()`` que lo toque
   falla por columna inexistente. Los tests de este addon usan únicamente
   instancias **no guardadas**, mismo criterio que
   ``tests/unit/account_qr_code_emv/test_res_bank.py``.
3. La migración de **datos** (semilla del tipo de servicio «Vendor Bill»,
   ``migrations/0001_seed_fleet_service_type_vendor_bill.py``) sí vive **en
   este addon** — no agrega columnas, sólo una fila en ``fleet.FleetServiceType``
   (tabla ya existente) + su identificador externo en ``ir.model.data`` (tabla
   de ``base``) — y no depende del wiring anterior para EXISTIR, sólo para
   ejecutarse (Django no corre migraciones de una app fuera de
   ``INSTALLED_APPS``).
"""
