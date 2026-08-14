"""``account_debit_note`` — nota de débito (Odoo ``account_debit_note``).

Adaptación de ``odoo19c: addons/account_debit_note/`` (``odoo-tools@
622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Ver el docstring de cada submódulo para el
detalle de qué se porta y qué queda deferido, con su razón.

Layout — igual que la referencia, con dos ausencias declaradas
=================================================================

La referencia trae ``models/``, ``security/``, ``tests/``, ``views/`` y
``wizard/``. Aquí:

- ``models/`` — se porta, con un archivo más (``account_move_sequence.py``,
  ver su docstring) por una razón mecánica, no de pereza.
- ``wizard/`` — se porta (``account.debit.note`` → ``TransientModel``, ≙
  ``base.BaseEnableProfilingWizard``).
- ``security/`` — se porta como docstring: la referencia sólo otorga acceso
  a la tabla del wizard (``account.group_account_invoice``), que aquí no
  tiene tabla (``TransientModel`` con ``managed = False``) ni vista DRF
  propia. Ver ``security/__init__.py``.
- ``tests/`` — en este árbol los tests unitarios viven fuera del addon, en
  ``tests/unit/account_debit_note/`` (convención del proyecto, no de la
  referencia).
- ``views/`` (3 archivos XML: botón, filtros, cabecera del reporte) y
  ``wizard/account_debit_note_view.xml`` — **NO se portan**: son artefactos
  del cliente web de Odoo (formulario, botones, plantilla QWeb del PDF). Sin
  equivalente DRF — no hay vista/serializer para este addon en este pase
  (mismo criterio que ``fleet.FleetVehicle`` con sus helpers
  ``ir.actions.act_window``, ver su docstring). La capacidad de negocio que
  esas vistas exponían (crear la nota, contar/listar las notas de un
  origen) SÍ se porta, como método invocable — ver ``models/account_move.py``
  y ``wizard/account_debit_note.py``.

Cobertura medida (conteo de símbolos de la referencia, por archivo)
=======================================================================

======================================  =========  =========  ===============
Archivo                                  Símbolos   Portados   No portados
======================================  =========  =========  ===============
``models/account_journal.py``                   2          2  0
``models/account_move.py``                      9          6  3 (nav./chatter)
``wizard/account_debit_note.py``               13          8  5 (sólo UI)
======================================  =========  =========  ===============

Total: 24 símbolos, 16 portados. Los 8 no portados están documentados en el
docstring del archivo que los habría alojado, con la medición que sustenta
la decisión — ninguno se omite en silencio (``porte-completo-no-parcial``).
"""
# Odoo importa aqui ``models``/``wizard``; en Django NO se puede: el
# ``__init__`` del app corre durante la carga del registro, antes de que
# ``apps.get_containing_app_config`` este listo, y cualquier modelo
# importado desde aqui revienta con ``AppRegistryNotReady``. Los modelos
# los descubre Django por convencion (``models/``); los overrides se
# cuelgan desde ``apps.py::ready()``. Mismo patron que ``l10n_mx`` y los
# otros cinco satelites, cuyo ``__init__`` esta vacio a proposito.
