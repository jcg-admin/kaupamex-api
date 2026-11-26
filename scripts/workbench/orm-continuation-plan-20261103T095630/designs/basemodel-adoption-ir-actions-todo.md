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

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsTodo` sobre `models.BaseModel` con los cinco atributos de clase | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:1352-1356` |
| `IrActionsTodo.create` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1362-1368` |
| `IrActionsTodo.write` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1370-1374` |
| `IrActionsTodo.ensure_one_open_todo` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1376-1380` |
| `IrActionsTodo.unlink` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1382-1392` |
| `IrActionsTodo.action_open` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1420-1422` |
| fila `ir_actions_todo group system` de `_ACCESS` | `src/addons/base/security/ir_model_access.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:104` |
| migración `0135_seed_ir_actions_todo_access` | `src/addons/base/migrations/0135_seed_ir_actions_todo_access.py` | ídem |

Prueba: `tests/unit/base/test_ir_actions_todo_basemodel.py`.

Anulaciones, restauradas con `cmp`:

- `create` sin `ensure_one_open_todo`: caen exactamente los dos casos de
  «un solo abierto» y pasa el de la ACL;
- `write` sin `ensure_one_open_todo`: cae exactamente
  `test_reopening_closes_the_other_open_step`;
- sin el cambio de base: caen los tres (los dos primeros porque
  `Environment(su=True)['ir.actions.todo']` no resuelve; el tercero por la
  ACL).

## Lo que esta unidad no cierra

- **`action_launch` (`:1394-1418`) no se porta: bloqueo medido.** Lee la
  acción con `self.env[action.type]`, y `ir.actions.actions` y sus subtipos
  no declaran `_name` aquí: `env['ir.actions.actions']` da
  `KeyError: 'ir.actions.actions'` (medido al escribir su prueba). Queda
  declarado en el docstring de la clase.
- **La rama de `base.open_menu` en `unlink` no tiene control**, por la misma
  causa: `base.action_client_base_menu` es un `ir.actions.client`, y ninguno
  de los dos registros se siembra.
- **Las tablas de los subtipos de acción no heredan de `ir_actions`.** La
  fuente las crea con `INHERITS (ir_actions)`
  (`odoo19c: odoo/addons/base/data/base_data.sql:9-13`); aquí cada subtipo
  tiene tabla propia, así que la FK `ir_actions_todo.action_id` sólo admite
  filas de `ir_actions` (`IntegrityError ... Key (action_id)=(1) is not
  present in table "ir_actions"`, medido con una acción de ventana).

Sucesor, para los tres: la adopción de `ir.actions.*` sobre
`models.BaseModel` dentro de `basemodel-adoption-0397` (TASK-API-0397). Su
condición de cierre es que `env['ir.actions.act_window']` resuelva y que una
acción de ventana pueda ser destino de `ir_actions_todo.action_id`; cómo
reproducir la herencia de tablas de PostgreSQL en Django es decisión de esa
unidad, no de ésta.

## Baseline del gate de idioma

`ensure_one_open_todo` entra en `scripts/identifier_language_baseline.txt`.
`todo` es aquí la palabra inglesa del nombre público de la fuente, y el
corpus del gate la lee como el español «todo». Renombrar el método rompería
el contrato con la referencia (`porte-completo-no-parcial.md`); el
precedente es la clase `IrActionsTodo`, ya listada. Las cuatro variables
locales que el gate marcaba se tradujeron (`records`, `record`,
`open_steps`, `open_menu_step`).
