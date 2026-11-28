# `ir.actions.todo`: `action_id` y `action_launch`

TASK-API-0397 (adopción de `ir.actions.*` sobre `models.BaseModel`).

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_actions.py:1347-1422`:

- `:1353` `_rec_name = 'action_id'`; `:1357` `action_id =
  fields.Many2one('ir.actions.actions', string='Action', required=True,
  index=True)`.
- `:1382-1392` `unlink`: `base.open_menu` no se borra; recupera
  `base.action_client_base_menu` como acción.
- `:1394-1418` `action_launch`: marca el paso `done`, lee la acción por su
  tipo (`self.env[action_type].browse(...)`, `read()[0]`); una acción que no
  es de ventana se devuelve tal cual; una de ventana recibe `context` (por
  defecto `'{}'`), evaluado con `safe_eval(..., {'user': self.env.user})`,
  saca `res_id` del contexto a la acción y fija `disable_log=True`.
- Los registros `base.action_client_base_menu` y `base.open_menu` se siembran
  en `odoo19c: odoo/addons/base/views/base_menus.xml:37-47`.

## Lo que el puerto tiene

- El campo se llama `action` (columna `action_id`) y `_rec_name` lo nombra
  así.
- `action_launch` falta. Su pendiente lo atribuía a dos causas que ya no
  existen: los subtipos de `ir.actions.*` declaran `_name` (p. ej.
  `IrActionsClient`, `ir_actions.py:1074`) y las tablas se heredan desde
  `0140_ir_actions_table_inheritance`.
- La rama de `base.open_menu` de `unlink` no tiene control: los dos registros
  no se siembran (la carga de `base_menus.xml` es otra unidad); la prueba los
  siembra con su `ir.model.data`.

## Cambio

1. `action` → `action_id` (forma C, `db_column='action_id'`), migración sólo
   de estado como `0148`; `_rec_name = 'action_id'`.
2. `action_launch` verbatim.
3. Consumidores de `action`/`todos` pasan a `action_id`.

## Pruebas

- RED: el campo se llama `action_id`; `action_launch` de una acción de
  ventana devuelve su `read()[0]` con `context` evaluado, `res_id` sacado del
  contexto y `disable_log`; una acción de cliente se devuelve sin contexto; el
  paso queda `done`; `unlink` de `base.open_menu` lo conserva con
  `base.action_client_base_menu`.
