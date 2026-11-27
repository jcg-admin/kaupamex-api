# binding_model_id, get_bindings y _get_bindings (paso 4c)

TASK-API-0397. Unidad: `ir-actions-bindings-0397`
(depende de `res-users-home-action-0397`).

## Referencia (odoo19c, odoo-tools@bf077302)

- `odoo/addons/base/models/ir_actions.py:74-75`: `binding_model_id`
  Many2one `ir.model`, `ondelete='cascade'`, con su help.
- `:155-182` `get_bindings`: por tipo de anclaje, descarta la acción cuyos
  `group_ids` no tiene el usuario (`has_group` por id externo) y la que su
  `res_model` no deja leer (`ir.model.access.check`, sin excepción).
- `:184-223` `_get_bindings` (`@tools.ormcache('model_name',
  'self.env.lang')`): `SELECT a.id, a.type, a.binding_type FROM ir_actions a
  JOIN ir_model m ON a.binding_model_id = m.id WHERE m.model = %s ORDER BY
  a.id`; lee de cada acción `name`, `binding_view_types` y, si existen,
  `group_ids` (pasados a ids externos con `_ensure_xml_id`), `res_model`,
  `sequence`, `domain` (descartado vacío); ordena `action` por `sequence`;
  descarta `MissingError`.
- `:269-276` `_check_model` (`act_window`): `binding_model_id.model` debe
  estar en el entorno.
- `:989-1000` (`server`) y `ir_actions_report.py:244-254` (`report`):
  `create_action` escribe `binding_model_id` (y `binding_type`);
  `unlink_action` comprueba `write` y lo vacía en los que lo tienen.

## Estado del árbol (medido)

- `IrActionsBase.binding_model_name` (`Char`, `ir_actions.py:305`) sustituye
  al Many2one; su docstring lo declara «conversión diferida a FK».
- `get_bindings` / `_get_bindings`: 0 definiciones en `src` y `addons`.
- Consumidores de `binding_model_name`: `IrActionsActWindow.clean`
  (`_check_model`), `IrActionsServer.create_action`/`unlink_action`,
  `IrActionsReport.create_action`/`unlink_action`, y dos pruebas
  (`test_ir_actions_constraints.py:142`,
  `test_ir_actions_server_runners.py:352,362`).
- Las seis tablas de acción heredan de `ir_actions` (migración 0140):
  `ADD COLUMN`/`DROP COLUMN` sobre `ir_actions` se propagan a las hijas, y una
  operación por modelo hija chocaría con la columna heredada. La migración
  opera sobre `ir_actions` en la base y sobre los seis modelos en el estado.

## Cambio

1. `IrActionsBase.binding_model_id` (forma C) en lugar de
   `binding_model_name`; migración: columna nueva en `ir_actions`, valor
   resuelto contra `ir_model.model`, retiro de la columna vieja.
2. `IrActionsActions.get_bindings` y `_get_bindings` con su `ormcache`.
3. `_check_model`, `create_action` y `unlink_action` de servidor y reporte
   sobre el Many2one.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsBase.binding_model_id` (forma C) en lugar de `binding_model_name` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:74-75` |
| `IrActionsBase.get_bindings` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:155-182` |
| `IrActionsBase._get_bindings` con `ormcache('model_name', 'self.env.lang')` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:184-223` |
| `IrActionsActWindow.clean` (`_check_model`) sobre `binding_model_id.model` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:269-276` |
| `IrActionsServer.create_action` y `unlink_action` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:989-1000` |
| `IrActionsReport.create_action` y `unlink_action` | `src/addons/base/models/ir_actions_report.py` | `odoo19c: odoo/addons/base/models/ir_actions_report.py:244-254` |
| migración `0147_ir_actions_bindings` | `src/addons/base/migrations/0147_ir_actions_bindings.py` | ídem |

Prueba: `tests/unit/base/test_ir_actions_bindings.py`, 5 casos.

Anulación (sobre una copia, restaurada y comparada con `cmp`): con el filtro
de grupos de `get_bindings` retirado, el orden por `sequence` invertido y la
escritura de `IrActionsServer.create_action` retirada caen exactamente los
tres casos que dependen de ellos (`3 failed, 2 passed`); los dos que
sobreviven miden la columna y el retiro del anclaje, que no dependen de esas
tres piezas.

- **La lectura de `_get_bindings` corre con `sudo()` del recordset**, como
  `self.env[action_model].sudo().browse(...)` de la fuente: el primer intento
  elevaba el entorno y no la lectura, y el caso del usuario sin el grupo
  terminaba en `PermissionDenied` en vez de filtrarse por `groups_id`.
- **El conteo de `test_domain_in_required` baja de 37 a 36.**
  `binding_model_name` era texto `NOT NULL` con dominio `in` requerido; el
  Many2one `binding_model_id` es anulable. Es evidencia fechada y se
  actualiza con su razón.
- **Las claves foráneas y los índices no se heredan** entre tablas
  (`0140`): la migración añade la columna una vez en `ir_actions` y la clave
  foránea `DEFERRABLE INITIALLY DEFERRED` y el índice por cada una de las
  seis tablas hijas.

## Defecto medido después del asentamiento

La primera `0147` retiraba `binding_model_name` sólo de `ir_actions`, con el
argumento de que `DROP COLUMN` sobre el padre se propaga a las hijas. Medido
al construir una base nueva (`pytest --create-db`, unidad 5b): es falso para
estas cinco tablas. `ir_act_window`, `ir_act_report_xml`, `ir_act_url`,
`ir_act_server` e `ir_act_client` ya tenían la columna cuando `0140` las hizo
heredar (`ALTER TABLE … INHERIT ir_actions`), así que la suya es **local**, y
PostgreSQL no retira de una hija la columna local que se retira del padre.
Quedaba `NOT NULL` y sin campo en el modelo: la siembra del cron de
`helpdesk` fallaba con `null value in column "binding_model_name" of relation
"ir_act_server"`.

`information_schema.columns` lo confirma en las dos formas de base: en
`orm_x2hokp_qa` (nueva) las cinco columnas siguen `NOT NULL`; en las bases
reutilizadas de los trabajadores (`_gw0`…) siguen presentes pero anulables,
que es por qué ni el subconjunto ni F2 (`--reuse-db`) lo vieron.

Corrección: `0147` retira la columna de las seis tablas (`DROP COLUMN IF
EXISTS`), y `0151` la retira en las bases que aplicaron la versión anterior.
La rama no está integrada, así que reescribir `0147` no afecta a una base
ajena; `0151` cubre las de esta máquina.
