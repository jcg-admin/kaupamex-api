"""``account_update_tax_tags`` — actualizar casillas fiscales (Odoo
``account_update_tax_tags``).

Adaptación de ``odoo19c: addons/account_update_tax_tags/`` (``odoo-tools@
622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Ver el docstring de cada submódulo para el
detalle de qué se porta y qué queda deferido, con su razón.

Layout — igual que la referencia, con un directorio de más y dos ausencias
================================================================================

La referencia trae ``i18n/``, ``security/``, ``tests/``, ``views/`` y
``wizard/`` (sin ``models/`` propio: su wizard opera directo sobre
``account.move.line``). Aquí:

- ``models/`` (**de más**, sin equivalente en la referencia) — los tres
  puentes hacia ``account.move.line`` que este pase construye porque
  ``tax_ids``/``tax_repartition_line_id``/``tax_tag_ids`` no están portados
  ahí y este pase no puede tocar ``account/``. Ver
  ``models/account_move_line_tax_link.py`` para la medición completa.
- ``wizard/`` — se porta entero (``account.update.tax.tags.wizard`` →
  ``TransientModel``, mismo patrón que ``account_debit_note``).
- ``security/`` — se porta como docstring: la referencia sólo otorga acceso
  a la tabla del wizard (``account.group_account_manager``), que aquí no
  tiene tabla ni vista DRF propia. Ver ``security/__init__.py``.
- ``tests/`` — en este árbol los tests unitarios viven fuera del addon, en
  ``tests/unit/account_update_tax_tags/`` (convención del proyecto, no de
  la referencia).
- ``views/`` (formulario del wizard + botón inyectado en ajustes de
  Contabilidad) — **NO se portan**: son artefactos del cliente web de Odoo,
  sin equivalente DRF en este pase (mismo criterio que
  ``account_debit_note``). La capacidad de negocio que exponían — recomputar
  casillas desde una fecha, sobre una empresa — SÍ se porta, como método
  invocable (``wizard/account_update_tax_tags_wizard.py``).
- ``i18n/`` — catálogo de traducciones del cliente web; sin equivalente
  (este stack no trae mecanismo de i18n de campos).

Cobertura medida (conteo de símbolos de la referencia, por archivo)
=======================================================================

======================================================  =========  =========  ===============
Archivo                                                    Símbolos   Portados   No portados
======================================================  =========  =========  ===============
``wizard/account_update_tax_tags_wizard.py``                     7          7  0
======================================================  =========  =========  ===============

Total: 7 símbolos, 7 portados. El mecanismo que la referencia da por
sentado (``account.move.line.tax_ids``/``tax_repartition_line_id``/
``tax_tag_ids``) no existe en ``account/`` — se construyó como modelos
puente propios de este addon (``models/``), no se fabricó adentro de
``account`` (fuera del límite de esta tarea) ni se dejó como bloqueo
diferido (``porte-completo-no-parcial.md``: "si el stack no trae el
mecanismo, se construye").
"""
# Odoo importa aqui ``models``/``wizard``; en Django NO se puede: el
# ``__init__`` del app corre durante la carga del registro, antes de que
# ``apps.get_containing_app_config`` este listo, y cualquier modelo
# importado desde aqui revienta con ``AppRegistryNotReady``. Los modelos
# los descubre Django por convencion (``models/``); el wizard (sin tabla,
# ``abstract = True``) no necesita descubrimiento — lo importa quien lo usa
# directamente. Mismo patron que ``account_debit_note`` y los demas
# satelites, cuyo ``__init__`` esta vacio a proposito.
