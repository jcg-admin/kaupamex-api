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
