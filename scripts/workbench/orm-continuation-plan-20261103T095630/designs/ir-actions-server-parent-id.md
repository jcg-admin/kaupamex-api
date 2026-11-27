# `parent_id` de `ir.actions.server` con el nombre de la fuente (5a)

TASK-API-0397. Depende de `ir-actions-constraints-0397`.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_actions.py:648-650`:

- `parent_id = fields.Many2one('ir.actions.server', string='Parent Action',
  index=True, ondelete='cascade')`.
- `child_ids = fields.One2many('ir.actions.server', 'parent_id', copy=True,
  ...)`: el inverso se declara contra `parent_id`.
- Consumidores en la fuente por ese nombre: `create` (`:711-728`, el hijo
  toma modelo y grupos del padre), `action_open_parent_action`
  (`:1328-1335`), `_get_children_domain` (`:870`), `_check_children`
  (`:967-973`, vía `@api.constrains('parent_id', 'child_ids')`) y la lista de
  dependencias de `warning` (`:745-757`).

## Estado del árbol (medido)

- El `Many2one` se llama `parent` (`src/addons/base/models/ir_actions.py:1545`)
  con columna `parent_id`; su comentario lo declara `≙ parent_id`.
- Usos del nombre local `parent` sobre acciones de servidor: el inverso
  (`:1558`), `action_open_parent_action` (`:1831`), `_check_children`
  (`:2451,2458`) y `create` (`:3016`, `vals.get('parent')`). `_get_children_domain`
  y `_warning_depends` ya escriben `parent_id`, que hoy no resuelve.
- Pruebas que lo usan: `test_ir_actions_constraints.py` (4 líneas),
  `test_ir_actions_server_basemodel.py` (1), `test_ir_actions_server_open.py`
  (5), `test_ir_actions_server_runners.py` (3) y
  `test_ir_actions_server_warning.py` (13). Los `parent` de
  `tests/fixtures/model_persisted_grid.py` son de `test_orm.category`, otro
  modelo.

## Cambio

1. `IrActionsServer.parent_id` en forma C (`db_column='parent_id'`,
   `related_name='+'`), `string='Parent Action'`, `index=True`,
   `ondelete='cascade'`; el inverso `child_ids` contra `'parent_id'`.
2. Los cuatro consumidores del modelo con el nombre de la fuente.
3. Migración de estado: `RenameField` y la columna explícita; la base no
   cambia (la columna ya es `parent_id`, en la tabla hija que hereda de
   `ir_actions`).
4. Las pruebas con `parent_id`.

## Fuera de esta unidad

`model_id` (5b, TASK-GEN-0391), y `_check_children`/`_check_python_code`
como `@api.constrains` junto con `automated_name` calculado (5c).

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsServer.parent_id` (forma C, `db_column='parent_id'`) en lugar de `parent`, e `IrActionsServer.child_ids` contra `'parent_id'` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:648-650` |
| `IrActionsServer.create` lee `vals['parent_id']` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:711-728` |
| `IrActionsServer.action_open_parent_action` con `self.parent_id.id` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1328-1335` |
| `IrActionsServer._check_children` recorre `parent_id` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:967-973` |
| prosa de `IrCron.action_open_parent_action` | `src/addons/base/models/ir_cron.py` | `odoo19c: odoo/addons/base/models/ir_cron.py:889-891` |
| migración `0148_ir_actions_server_parent_id`, sólo de estado | `src/addons/base/migrations/0148_ir_actions_server_parent_id.py` | ídem |

Prueba: `test_parent_id_keeps_the_source_name` en
`tests/unit/base/test_ir_actions_server_open.py`, más las pruebas de acción de
servidor que crean o leen el padre, con el nombre de la fuente. RED antes del
cambio: 5 fallidos en los cinco archivos de acción de servidor; Django
aceptaba `parent_id=` porque era el `attname` del campo `parent`, y eso
ocultaba el resto.

Anulación (copia restaurada y comparada con `cmp`): con `create` leyendo
`vals.get('parent')` cae exactamente
`test_creating_a_child_copies_the_model_and_groups_of_the_parent`.

- **La migración es sólo de estado.** El `RenameField` que Django genera
  renombra la columna a `parent_id_id`, retira y recrea la clave foránea y
  vuelve a renombrarla; con `SeparateDatabaseAndState` el `sqlmigrate` da
  `(no-op)`: la columna, su clave foránea y su índice ya eran `parent_id`.
- **Un consumidor que la búsqueda inicial no vio:**
  `tests/integration/base/test_copy_follows_the_one2many_copy_flag.py`, que
  no nombra `IrActionsServer` en la línea de `parent=`. Lo destapó el
  subconjunto derivado (`2 failed, 1269 passed`); el otro rojo es el
  heredado de `test_default_get`, que también falla sobre HEAD.
- **Prosa heredada corregida:** el docstring del módulo y dos docstrings
  afirmaban que el campo se llama `parent`.
