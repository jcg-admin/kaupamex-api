# La familia ir.actions.* sobre BaseModel y con la herencia de tablas

Unidad de `basemodel-adoption-0397` (TASK-API-0397). Directiva del ejecutor
(2026-11-26): un bloqueo por una pieza ausente no autoriza a diferir el
símbolo que depende de ella; la pieza se construye. Esta unidad es la que
desbloquea `ir.actions.todo.action_launch`, la rama de `base.open_menu` en
su `unlink`, `ir.module.module.next` y `ir.demo_failure.wizard.done`, que
quedaron declarados pendientes en
`designs/basemodel-adoption-ir-actions-todo.md` y
`designs/basemodel-adoption-ir-demo-failure.md`. Esas declaraciones de
pendiente se retiran al cerrar esta unidad.

## Fuente medida

- `odoo19c: odoo/addons/base/data/base_data.sql:5-13`: `ir_actions` es la
  tabla madre (`id serial`) y `ir_act_window`, `ir_act_report_xml`,
  `ir_act_url`, `ir_act_server` e `ir_act_client` se crean
  `INHERITS (ir_actions)`: comparten la secuencia de ids y un `SELECT` sobre
  `ir_actions` devuelve también las filas de los subtipos.
- `odoo19c: odoo/orm/fields_relational.py:313-314`: un Many2one cuyo
  comodelo tiene tabla `ir_actions` **no crea clave foránea** («ir_actions
  is inherited, so foreign key doesn't work on it»).
- Cada subtipo declara `_name` y `_inherit = 'ir.actions.actions'` con
  `_table` propio (`odoo19c: odoo/addons/base/models/ir_actions.py`).

## Estado medido del puerto (base de pruebas, 2026-11-26)

- `IrActionsBase` (`src/addons/base/models/ir_actions.py:258`) es abstracto
  sobre `TimeStampedModel`; sólo `ir.actions.server` e
  `ir.actions.report` declaran `_name`, y ninguno es `models.BaseModel`:
  `Environment()['ir.actions.actions']` da `KeyError`.
- Las cinco tablas de subtipo tienen todas las columnas de `ir_actions` con
  el mismo tipo (0 faltantes, 0 tipos distintos), así que admiten
  `ALTER TABLE ... INHERIT ir_actions`.
- Filas: `ir_actions` 0, `ir_act_server` 9 (id máximo 98), el resto 0. Una
  secuencia común no obliga a renumerar.
- Claves foráneas hacia `ir_actions` que la fuente no crea:
  `ir_actions_todo.action_id`, `ir_embedded_actions.action_id`,
  `ir_filters.action_id`, `account_report_line.action_id`.

## Cambio, en pasos con su propio F2

1. **Herencia de tablas.** Migración: `INHERIT ir_actions` en las cinco
   tablas, su `id` con el `nextval` de la secuencia de `ir_actions` y la
   secuencia puesta por encima del máximo de las seis; las cuatro claves
   foráneas hacia `ir_actions`, retiradas, y la regla de
   `fields_relational.py:313-314` aplicada en la declaración del campo para
   que una migración nueva no la vuelva a crear.
2. **`_name` y `models.BaseModel`** en `ir.actions.actions` y sus
   subtipos, con la ACL de la fuente y la elevación de los escritores que
   la fuente hace con `sudo()`; el mapa de consumidores decide si va en uno o
   en varios pasos.
3. **Los símbolos desbloqueados**: `IrActionsTodo.action_launch`, la rama
   de `base.open_menu`, `IrModuleModule.next` y
   `IrDemoFailureWizard.done`, con sus pruebas.

El mapa de consumidores lo prepara un subagente de sólo lectura y se anexa
aquí antes del paso 2.
