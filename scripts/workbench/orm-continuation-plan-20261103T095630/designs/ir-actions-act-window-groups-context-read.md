# group_ids, context y read de la acción de ventana (paso 3b)

Unidad de `basemodel-adoption-0397` (TASK-API-0397), subunidad 3b del paso 3
de `ir-actions-family-basemodel-and-inheritance.md`. Sigue a
`ir-actions-act-window-basemodel.md` (3a, asentada).

## Fuente medida

- `group_ids = fields.Many2many('res.groups', 'ir_act_window_group_rel',
  'act_id', 'gid', string='Groups')`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:328-329`).
- `context = fields.Char(string='Context Value', default={}, required=True)`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:312-313`): texto de una
  expresión de Python.
- `read` (`odoo19c: odoo/addons/base/models/ir_actions.py:341-355`): si se
  pide `help` (o todos los campos), evalúa `context` con `safe_eval` y pide
  al modelo destino `get_empty_list_help(help)`.
- `get_empty_list_help` es del modelo `base`, que todo modelo recibe
  (`odoo19c: odoo/addons/base/models/ir_ui_view.py:2728-2758`): devuelve el
  mensaje tal cual.

## Puerto antes del paso

- El campo se llama `groups`; su tabla es `ir_act_window_group_rel` con las
  columnas `iractionsactwindow_id` y `resgroups_id` (medido sobre el modelo).
  Lectores de `groups` en `src/`, `addons/` y `tests/`: 0.
- `context` es `Json` con `default=dict`. Ningún consumidor lee el `context`
  guardado de una acción de ventana como dict: los addons que abren acciones
  devuelven dicts literales (`addons/crm/models/crm_lead.py:2094`), y
  `_for_xml_id` sólo lo llama `src/addons/base/models/ir_actions_report.py`.
- `read` no se sobrescribe. `get_empty_list_help` no existe en
  `models.BaseModel`: sólo lo definen `crm.lead` y `stock.picking`, como
  sobrescrituras. `Base` de `src/addons/base/models/ir_model.py:321` es
  abstracto y ningún modelo hereda de él, así que el sitio de los métodos
  del modelo `base` es `models.BaseModel`.

## Cambio

1. `group_ids` con `relation='ir_act_window_group_rel'`, `column1='act_id'`
   y `column2='gid'`. La migración renombra el campo en el estado y las dos
   columnas en la base (`SeparateDatabaseAndState`): las filas se conservan.
2. `context` pasa a `Char` con `default='{}'`. La migración cambia el tipo
   de la columna y reescribe cada valor con `repr` del dict guardado: es el
   literal de Python que `safe_eval` lee (`json.dumps` escribiría `true`,
   `false` y `null`, que no lo son).
3. `IrActionsActWindow.read` como la fuente.
4. `BaseModel.get_empty_list_help` como la fuente.

Fuera de 3b: el resto de los métodos del modelo `base` de `ir_ui_view.py`
(`get_views`, `view_header_get`, `_get_default_*_view`) es la unidad de
`get_views` del plan.

## Controles previstos

- `group_ids` lee y escribe la relación de la fuente, con las columnas
  `act_id` y `gid` en la base;
- `context` guarda texto y por defecto `'{}'`;
- un dict guardado antes de la migración sale como literal de Python
  (`{'a': True}`, no `{"a": true}`);
- `read(['help'])` devuelve lo que `get_empty_list_help` del modelo destino
  devuelve, con el `context` de la acción en el entorno;
- `BaseModel.get_empty_list_help` devuelve el mensaje sin tocarlo.

Prueba: `tests/unit/base/test_ir_actions_act_window_groups_context.py`.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| campo `group_ids` de `IrActionsActWindow` con `relation`, `column1` y `column2` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:328-329` |
| campo `context` de `IrActionsActWindow` como `Char` con `default='{}'` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:312-313` |
| `IrActionsActWindow.read` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:341-355` |
| `BaseModel.get_empty_list_help` | `src/orm/models.py` | `odoo19c: odoo/addons/base/models/ir_ui_view.py:2747-2758` |
| migración `0142_ir_actions_act_window_groups_context` y su `context_as_python_literal` | `src/addons/base/migrations/0142_ir_actions_act_window_groups_context.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:312-329` |

Prueba: `tests/unit/base/test_ir_actions_act_window_groups_context.py`, 5
casos. RED antes del cambio: 4 fallidos (el quinto, el de la migración, se
añadió con ella). GREEN: 5.

`makemigrations` proponía `RemoveField` + `AddField` para `group_ids`, que
borraría las filas de la relación; la migración renombra el campo sólo en
el estado y las dos columnas en la base. `sqlmigrate` da los dos `RENAME
COLUMN` y el `ALTER COLUMN context TYPE varchar USING context::varchar`.

Tres hechos medidos al probar:

- `res.groups` no es `BaseModel`: `group_ids` se lee como `AccessQuerySet`
  y no tiene `.ids`; la prueba compara con `values_list`.
- El `with_context(**ctx)` de `read` pone el contexto en el entorno del
  recordset, y las sobrescrituras de la fuente lo leen con
  `self.env.context`. La prueba mide eso, sobre un modelo destino que es
  `BaseModel` (`ir.actions.server`): con `res.partner`, que no lo es,
  `env[model]` devuelve la clase y no hay recordset.
- El `except:` de la fuente se escribe `except Exception:`. El gate de
  estilo usa pycodestyle (`scripts/check_python_style_increment.py:24`),
  que rechaza el `except:` desnudo (E722); no se añade `noqa`.
