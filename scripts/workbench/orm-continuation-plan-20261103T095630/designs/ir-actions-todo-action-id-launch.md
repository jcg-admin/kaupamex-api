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

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsTodo.action_id` (forma C, `db_column='action_id'`, `related_name='+'`) y `_rec_name = 'action_id'` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:1353-1357` |
| `IrActionsTodo.action_launch` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1394-1418` |
| `IrActionsTodo.unlink`: la rama de `base.open_menu` escribe `action_id` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1382-1392` |
| `Binary.column_type`: `bytea` sin adjunto, sin columna con adjunto | `src/orm/fields_binary.py` | `odoo19c: odoo/orm/fields_binary.py:40-42` |
| migración `0154_ir_actions_todo_action_id`: sólo de estado | `src/addons/base/migrations/0154_ir_actions_todo_action_id.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:1357` |

Medido al implementar: `action_launch` lee la acción con `read()[0]`, y
`read()` de una acción de cliente moría en `params_store` con
`NotImplementedError: Method read() undefined`, porque el `Binary` del puerto
no declaraba `column_type`. Se porta el de la fuente.

`scripts/fk_naming_baseline.txt` pierde la línea `IrActionsTodo.action`: era
la deuda de nombre que esta unidad salda.

Prueba: `tests/unit/base/test_ir_actions_todo_launch.py`, 5 casos (RED: 5 de
5).

Anulación, cada pieza por separado (copias restauradas y comparadas con
`cmp`): sin `Binary.column_type` cae el caso de la acción de cliente; sin la
rama de `base.open_menu`, el de `unlink`; sin sacar `res_id` del contexto, el
de la acción de ventana. Un caso por pieza, ninguno más.

Subconjunto derivado (archivos que nombran `ir.actions.todo`,
`IrActionsClient`, `fields.Binary` o `params_store`): `185 passed, 3 xfailed`.

El primer F2 (`2018f827`, 15094 aprobadas) subió los `xfailed` de 8 a 9: la
matriz de `tests/unit/orm/test_delete_policy_contract.py` lee las filas de
`outputs/fk_reference_ondelete.tsv`, evidencia fechada que nombra el campo
`action`; tras el renombre `get_field('action')` levantaba y el caso, sin su
clave en `CORRECTED`, quedaba en `xfail` estricto. Un contrato no se cierra
por `xfail`: la prueba lee el campo por su nombre nuevo con `RENAMED`, y la
fila conserva su identidad y su entrada en `CORRECTED`.
