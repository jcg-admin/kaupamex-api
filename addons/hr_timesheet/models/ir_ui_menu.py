"""``ir.ui.menu`` — poda de menú por rol de hoja de horas (Odoo
``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/ir_ui_menu.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 13 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte DIFERIDO — 0 de 1 símbolo, mecanismo disponible pero fuera de
alcance de este pase
========================================================================

Medido por AST: 1 clase (``_inherit``), 1 método (``_load_menus_blacklist``).

======================================  ==================================
Símbolo de la referencia (línea)         Estado
======================================  ==================================
``_load_menus_blacklist`` (:9-13)        diferido
======================================  ==================================

**No es un bloqueo por mecanismo ausente** — ``hr/models/ir_ui_menu.py``
(este mismo árbol) ya porta el mismo método sobre ``base.IrUiMenu`` con
``orm.model_classes.extend_model`` (``campos``/``metodos``/``luego``),
consultando ``base.ResUsers.has_group`` (existe,
``src/addons/base/models/res_users.py:518``) y el campo ``key`` de
``base.IrUiMenu`` como equivalente del xmlid. El mecanismo existe.

Se difiere en este pase por dos razones, ambas de **datos**, no de
esquema:

1. Necesita el grupo sembrado ``hr_timesheet.group_hr_timesheet_approver``
   y la fila de menú ``hr_timesheet.timesheet_menu_activity_user`` — ambas
   son data de instalación (``ir.model.data``/seed), fuera del alcance de
   un addon que porta esquema.
2. **Sin consumidor cableado** — igual que ``web/models/ir_ui_menu.py::
   load_web_menus`` (citado en el propio ``hr/models/ir_ui_menu.py``):
   ``CapabilityPrunedMenuManager.load_menus`` no consulta ninguna
   blacklist todavía.

Sucesor: aplicar el mismo patrón que ``hr/models/ir_ui_menu.py``
(``extend_model('base', 'IrUiMenu', metodos={...})``) cuando el resto de
la maquinaria de hoja de horas (menú, grupos, capacidades) se cablee.
"""


def apply_hr_timesheet_ir_ui_menu_extensions():
    """No-op declarado — ver el docstring del módulo."""
    return None
