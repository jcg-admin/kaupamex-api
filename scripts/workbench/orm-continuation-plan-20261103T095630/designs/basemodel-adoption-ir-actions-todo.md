# ir.actions.todo sobre BaseModel, con su conducta

Unidad de `basemodel-adoption-0397` (TASK-API-0397). Mapa de consumidores
preparado por un subagente de sólo lectura y verificado contra la fuente.

## Fuente medida

`odoo19c: odoo/addons/base/models/ir_actions.py:1347-1422`:

- `_name = 'ir.actions.todo'`, `_description = "Configuration Wizards"`,
  `_rec_name = 'action_id'`, `_order = "sequence, id"`,
  `_allow_sudo_commands = False` (`:1352-1356`).
- `create` y `write` llaman a `ensure_one_open_todo` cuando el estado queda
  `open` (`:1363-1375`); `ensure_one_open_todo` busca los abiertos en orden
  `sequence asc, id desc` con `offset=1` y los pasa a `done` (`:1377-1381`):
  queda abierto sólo el de menor secuencia y mayor id.
- `unlink` no borra `base.open_menu`: le devuelve la acción
  `base.action_client_base_menu` y lo saca del conjunto; un `ValueError` de
  `env.ref` se ignora (`:1383-1393`).
- `action_launch` marca `done`, lee la acción y, si es `act_window`, evalúa
  su contexto, mueve `res_id` y fija `disable_log` (`:1395-1418`).
  `action_open` vuelve a `open` (`:1420-1422`).

ACL: `access_ir_actions_todo`, `group_system`, 1,1,1,1
(`odoo19c: odoo/addons/base/security/ir.model.access.csv:104`). Sin reglas.

## Puerto antes de la unidad

`src/addons/base/models/ir_actions.py:2644-2680`: sólo campos (`action`
PROTECT, `sequence`, `state`, `name`) y `Meta.ordering`. Faltan los seis
métodos y los cinco atributos de clase; no hay fila de ACL. Ningún llamador
de producción; dos pruebas crean filas
(`tests/unit/orm/test_delete_policy_contract.py`,
`tests/unit/base/test_restrict_ondelete_country_todo.py`).

## Cambio

1. `IrActionsTodo(models.BaseModel, TimeStampedModel)` con los cinco
   atributos de clase.
2. `create`, `write`, `ensure_one_open_todo`, `unlink`, `action_launch` y
   `action_open`, en el orden de la fuente y al final de la clase.
3. Fila de ACL `access_ir_actions_todo` para `group_system`.
4. Las dos pruebas que crean filas sin usuario se elevan.

`base.open_menu` no se siembra aquí; el `unlink` portado lo busca con
`IrModelData._xmlid_to_res_id(..., raise_if_not_found=False)` y sigue si no
existe, que es el `except ValueError: pass` de la fuente.

## Controles previstos

- dos `open` con secuencias distintas: sólo queda abierto el de menor
  secuencia;
- `action_launch` de una `act_window` con `res_id` en el contexto devuelve
  el `res_id` fuera del contexto y `disable_log`;
- un usuario interno sin `group_system` no crea filas (ACL);
- `unlink` de `base.open_menu`, cuando existe, no lo borra.

Prueba: `tests/unit/base/test_ir_actions_todo_basemodel.py`.
