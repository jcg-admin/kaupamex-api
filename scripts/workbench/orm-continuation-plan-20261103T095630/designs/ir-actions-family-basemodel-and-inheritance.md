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

## Mapa de consumidores (subagente de sólo lectura, 2026-11-26)

**ACL de la fuente** (`odoo19c: odoo/addons/base/security/ir.model.access.csv:100-110`):
`group_system` 1,1,1,1 para `actions`, `act_window`, `act_window_close`,
`report`, `todo`, `act_window_view`, `act_url`, `server` y `client`;
`server_history` 1,1,1,0. Sin reglas para `ir.actions.*`. En `_ACCESS`
faltan `IrActionsActions`, `IrActionsActWindow`, `IrActionsActWindowClose`,
`IrActionsActWindowView`, `IrActionsActUrl` e `IrActionsClient`.

**Métodos de la fuente sin contraparte** (a portar, no a declarar):

| Clase | Métodos |
|---|---|
| `ir.actions.actions` | `_check_path`, `_compute_xml_id`, `create`, `write`, `unlink`, `_unlink_check_home_action`, `get_bindings`, `_get_bindings` |
| `ir.actions.act_window` | `_check_model`, `_compute_views`, `_check_view_mode`, `_compute_embedded_actions`, `read`, `create`, `unlink`, `exists`, `_existing`, `_get_action_dict` |
| `ir.actions.act_window_close`, `ir.actions.act_url` | `_get_readable_fields` |
| `ir.actions.client` | `_compute_params`, `_inverse_params` |
| `ir.actions.server` | `create`, `write`, `create_action`, `unlink_action` |
| `ir.actions.report` | `_render_qweb_text` |

Cada fila se verifica contra la fuente antes de su paso; el subagente
comparó listas de nombres, no cuerpos.

**Consumidores que tocan la ACL.** Producción: `ir_cron.py`,
`data/cron.py`, `wizard/wizard_ir_model_menu_create.py`,
`addons/base_automation/models/base_automation.py`, lecturas de
`IrActionsActWindow` en `stock_picking.py:920` y `stock_quant.py:1016`, y
`env['ir.actions.*']` en `ir_cron.py`, `ir_field_converters.py`,
`account/models/res_partner_bank.py` y `account_fleet/models/fleet_vehicle.py`.
Pruebas: `tests/unit/base_automation/test_crud_and_actions_server.py` y las
de `ir_actions_server_*`, `ir_actions_constraints`, `ir_model_ondelete`,
`cron_xml_id_identity`, más unas 30 con 1-3 usos. Las migraciones escriben
por `objects` y no tocan la ACL.

**Extensores:** `_inherit = 'ir.actions.report'` en `stock` y `sale`
(y menciones en `account` y `account_edi_ubl_cii`);
`IrActionsActWindowClose` hereda de `IrActionsActions`.

**Riesgos:** el cron y `base_automation` ejecutan acciones de servidor sin
usuario; una fila de `_ACCESS` ausente niega a todos.

## Orden de pasos, revisado con el mapa

1. Herencia de tablas y claves foráneas (sin cambio de base): no toca la
   ACL y se mide sola.
2. `ir.actions.server` (+ `server.history`) e `ir.actions.report`, con sus
   métodos faltantes y la elevación del cron y de `base_automation`.
3. `act_window`, `act_window_view`, `act_window_close`, `act_url`,
   `client`, con sus filas de `_ACCESS` y sus métodos.
4. `ir.actions.actions`, con `get_bindings` y los demás.
5. `IrActionsTodo.action_launch` y la rama de `base.open_menu`,
   `IrModuleModule.next`, `IrDemoFailureWizard.done`.

## Paso 1 — detalle medido antes de escribirlo

- Las seis tablas tienen `id` como columna de identidad (`GENERATED BY
  DEFAULT AS IDENTITY`), cada una con su secuencia. La herencia de
  PostgreSQL no comparte identidad: los cinco subtipos pierden la suya y su
  `id` toma por defecto el `nextval` de la secuencia de `ir_actions`, que
  se adelanta al máximo de las seis tablas (hoy 98, en `ir_act_server`).
- Los cuatro campos con clave foránea hacia `ir_actions`:
  `IrActionsTodo.action` (`src/addons/base/models/ir_actions.py`),
  `IrEmbeddedActions.action` (`src/addons/base/models/ir_embedded_actions.py:127`),
  `IrFilters.action_id` (`src/addons/base/models/ir_filters.py:91`) y
  `AccountReportLine.action` (`addons/account/models/account_report.py:525`).
  Llevan `db_constraint=False`, la regla de
  `odoo19c: odoo/orm/fields_relational.py:313-314` escrita en el campo, y
  una prueba recorre todos los modelos y exige que ninguna clave foránea
  apunte a `ir_actions`, para que un campo nuevo no la vuelva a crear.
- `ir_embedded_actions.parent_action` apunta a `ir_act_window`, no a
  `ir_actions`: la fuente sí crea esa clave, y se queda.

Controles: un `SELECT` sobre `ir_actions` ve una fila insertada en
`ir_act_server` (herencia); dos subtipos no reparten el mismo id
(secuencia común); un paso de `ir.actions.todo` apunta a una acción de
ventana (sin clave foránea), que es el caso que hoy da `IntegrityError`.

## Paso 1 — lo implementado y lo medido

Un control de la lista de arriba se cambió al medirlo: «dos subtipos no
reparten el mismo id» pasaba también **antes** de la migración, porque las
secuencias propias daban ids distintos por casualidad de estado. No
discriminaba. Se sustituyó por el que sí: el `id` de cada subtipo toma por
defecto el `nextval` de la secuencia de `ir_actions` (antes, `None`:
columna de identidad sin `DEFAULT`).

Piezas:

- `src/addons/base/migrations/0140_ir_actions_table_inheritance.py`:
  tres `AlterField` con `db_constraint=False` (`IrActionsTodo.action`,
  `IrEmbeddedActions.action`, `IrFilters.action_id`) y un `RunSQL` que, por
  cada subtipo, quita la identidad, fija `DEFAULT nextval` de la secuencia
  de `ir_actions`, declara `INHERIT ir_actions` y adelanta la secuencia al
  máximo de las seis tablas. Es el `base_data.sql:5-13` de la fuente
  (`odoo19c: odoo/addons/base/data/base_data.sql:5-13`).
- `addons/account/migrations/0059_account_report_line_action_without_fk.py`:
  el `AlterField` de `AccountReportLine.action`, que depende de la 0140.
- Los cuatro campos llevan `db_constraint=False` con la cita a
  `odoo19c: odoo/orm/fields_relational.py:313-314` en un comentario.

Pruebas: `tests/unit/base/test_ir_actions_table_inheritance.py`, 14
casos. RED antes de la migración: 7 fallidos y 1 error. GREEN: 14.

Anulación, restaurada con `cmp`: con `db_constraint=True` de vuelta en
`IrFilters.action_id` cae exactamente `test_no_foreign_key_points_at_ir_actions`
(1 fallido, 13 pasan).

Subconjunto derivado (75 archivos que nombran la familia, `-n 4`): 1218
pasan y caen dos, las dos con causa medida:

- `tests/unit/orm/test_delete_policy_contract.py` afirmaba que un
  `DELETE` en SQL de una acción con un paso de `ir.actions.todo` falla por
  la clave foránea. Esa clave es la que la fuente no crea
  (`odoo19c: odoo/orm/fields_relational.py:313-314`). La prueba pasa a
  afirmar el contrato de la fuente: el `DELETE` crudo no cascada y deja el
  paso apuntando a un id que ya no existe. La política de borrado por el
  ORM sigue cubierta por el caso de la matriz.
- `test_the_cron_is_seeded` de la unidad `res.users.deletion`: la
  migración `0137` siembra el cron, pero `tests/conftest.py` no lo
  re-siembra tras el `flush` de una prueba transaccional, y en paralelo
  depende del orden. Era un defecto latente de esa unidad, no de ésta. Se
  añade `CRON_RES_USERS_DELETION` a `_CRON_SPECS`.

Con los dos arreglos: 121 pasan y 2 `xfail` sobre los cuatro archivos
afectados, `-n 4`.
