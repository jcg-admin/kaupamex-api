# ir.actions.act_window sobre BaseModel (paso 3a)

Unidad de `basemodel-adoption-0397` (TASK-API-0397), paso 3 del plan de
`ir-actions-family-basemodel-and-inheritance.md`, cortado en tres
subunidades (3a, 3b, 3c) para que cada una tenga su propio F2. Mapa de
consumidores preparado por un subagente de sólo lectura y verificado
contra la fuente.

## Fuente medida

- Atributos: `odoo19c: odoo/addons/base/models/ir_actions.py:262-267`
  (`_name`, `_description = 'Action Window'`, `_table`, `_inherit`,
  `_order = 'name, id'`, `_allow_sudo_commands = False`).
- `view_id` Many2one a `ir.ui.view`, `ondelete='set null'`, y
  `search_view_id` (`odoo19c: odoo/addons/base/models/ir_actions.py:309-331`).
- `_compute_embedded_actions`, `create`, `unlink`, `exists`, `_existing`,
  `_get_readable_fields` y `_get_action_dict`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:336-397`): `create`
  nombra la acción con la `_description` de su modelo si llega sin nombre y
  limpia la caché del registro, igual que `unlink`; `exists` filtra por el
  conjunto de ids que `_existing` memoriza.
- ACL `access_ir_actions_act_window_system`, `group_system`, 1,1,1,1
  (`odoo19c: odoo/addons/base/security/ir.model.access.csv:101`).

## Puerto antes del paso

`IrActionsActWindow(IrActionsBase)`: modelo de Django, sin atributos de
clase ni `view_id` ni `search_view_id` (la propiedad `views` lee
`getattr(self, 'view_id', None)`, que siempre es `None`). Ninguno de los
siete métodos. Sin fila de ACL.

## Cambio

1. `IrActionsActWindow(models.BaseModel, IrActionsBase)` con sus seis
   atributos de clase.
2. `view_id` y `search_view_id` con su migración.
3. Los siete métodos de la fuente.
4. Fila de `_ACCESS` y su siembra.
5. Consumidores: `views` deja `view_ids.all()`; `src/tools/convert.py` lee
   la acción del `menuitem` dentro del `sudo()` de la carga de datos.

Fuera de 3a, en 3b: `group_ids` con el nombre de la fuente, `context` como
`Char` con migración de datos y `read` con `get_empty_list_help`.

En 3d, después de 3c: `_compute_embedded_actions` y el `_get_action_dict`
de la acción de ventana. Los dos leen `ir.embedded.actions.is_visible`, que
en la fuente es un campo calculado (`_compute_is_visible`,
`odoo19c: odoo/addons/base/models/ir_embedded_actions.py:77-96`) y en el
puerto es un método con otra firma sobre un modelo que no es `BaseModel`.
Portarlos exige primero esa conversión; 3d la hace.

## Controles previstos

- un administrador del sistema crea una acción de ventana;
- un usuario interno no la lee;
- crear sin nombre toma la `_description` del modelo destino;
- `views` antepone la vista de `view_id` cuando su tipo falta en
  `view_ids`;
- `exists` devuelve las acciones vivas y, tras `unlink`, ya no la del id
  borrado: `unlink` limpia la caché que `_existing` memoriza;
- `_get_readable_fields` incluye `view_id`, `search_view_id` y
  `embedded_action_ids`.

Prueba: `tests/unit/base/test_ir_actions_act_window_basemodel.py`.

## Directiva del ejecutor (2026-11-27), durante 3a

*«es un error se te olvida que tienes tienes PROHIBIDO realizar deducciones
… debes de implementarlo en kaupamex-api, como lo hace la referencia»*,
sobre el docstring de `IrActionsBase._get_readable_fields`, que explicaba
por qué el método vive en `IrActionsBase` con un razonamiento propio («el
método vive en el portador, porque es de quien heredan los subtipos»).

Corregido con hechos medidos: la fuente declara el método en
`ir.actions.actions`
(`odoo19c: odoo/addons/base/models/ir_actions.py:55-60`) y cada subtipo lo
recibe por `_inherit = ['ir.actions.actions']`; el árbol traduce un
`_inherit` dentro de la misma app a herencia de Python desde una base
abstracta (`src/orm/model_classes.py:20`), y esa base es `IrActionsBase`.
El docstring de `IrActionsBase` se reescribió igual.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsActWindow` sobre `models.BaseModel` con sus seis atributos | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:262-267` |
| campos `view_id` y `search_view_id` de `IrActionsActWindow`, en forma C | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:309-331` |
| `IrActionsActWindow.create`, `unlink`, `exists`, `_existing`, `_get_readable_fields` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:357-386` |
| `IrActionsActWindow.views` lee `view_id` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:282-296` |
| docstrings de `IrActionsBase` y `IrActionsBase._get_readable_fields` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:55-60` |
| fila `ir_actions_act_window_system` de `_ACCESS` | `src/addons/base/security/ir_model_access.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:101` |
| migración `0141_ir_actions_act_window_views` | `src/addons/base/migrations/0141_ir_actions_act_window_views.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:309-331` |
| `XmlImport._tag_menuitem` lee la acción dentro del `sudo()` | `src/tools/convert.py` | `odoo19c: odoo/tools/convert.py:305-309` |

Prueba: `tests/unit/base/test_ir_actions_act_window_basemodel.py`, 7 casos.
RED antes del cambio: 7 fallidos. GREEN: 7.

`view_ids` sigue leyéndose con `.all()`: `IrActionsActWindowView` no es
`BaseModel` hasta 3c, y su acceso inverso es todavía el gestor de Django.
