# act_window.view, act_url y client sobre BaseModel (paso 3c)

Unidad de `basemodel-adoption-0397` (TASK-API-0397), subunidad 3c del paso 3
de `ir-actions-family-basemodel-and-inheritance.md`. `act_window_close`, que
el plan ponía aquí, es un proxy de `IrActionsActions` en el puerto y no
puede ser `BaseModel` antes que su padre: pasa al paso 4, con
`ir.actions.actions`.

## Fuente medida

- `ir.actions.act_window.view`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:411-425`): `_rec_name =
  'view_id'`, `_order = 'sequence,id'`, `_allow_sudo_commands = False`,
  `UniqueIndex('(act_window_id, view_mode)')`; `view_id` Many2one a
  `ir.ui.view`; `act_window_id` Many2one a `ir.actions.act_window` con
  `ondelete='cascade'`.
- `ir.actions.act_url`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:445-460`): `url` Text
  obligatorio, `target` obligatorio con default `'new'`,
  `_get_readable_fields` con `target`, `url` y `close`.
- `ir.actions.client`
  (`odoo19c: odoo/addons/base/models/ir_actions.py:1426-1462`): `context`
  Char con default `"{}"`; `params` calculado con inverso
  (`_compute_params` evalúa `params_store` con `safe_eval`,
  `_inverse_params` guarda `repr` del dict); `params_store`;
  `_get_readable_fields` con `context`, `params`, `res_model`, `tag` y
  `target`.
- ACL `group_system` 1,1,1,1 de los tres
  (`odoo19c: odoo/addons/base/security/ir.model.access.csv:105-110`).

## Puerto antes del paso

- `IrActionsActWindowView(TimeStampedModel)`: `view_id` es `Integer`; la
  FK a la acción se llama `act_window`.
- `IrActionsActUrl(IrActionsBase)` e `IrActionsClient(IrActionsBase)`:
  modelos de Django sin atributos de clase. `client` guarda `context` y
  `params_store` como `Json` y no tiene `params`.
- Ninguno tiene fila de ACL.

## Cambio

1. Los tres sobre `models.BaseModel` con sus atributos de clase.
2. `act_window.view`: `view_id` como Many2one a `ir.ui.view` y la FK a la
   acción como `act_window_id`, los dos en forma C; `view_ids.all()` de
   `IrActionsActWindow.views` pasa al recordset.
3. `act_url`: `url` obligatorio, `target` obligatorio con default `'new'`,
   y `_get_readable_fields`.
4. `client`: `context` como `Char`, `params_store` como texto con su
   migración de datos (el JSON guardado pasa a `repr` del dict), `params`
   calculado con `_compute_params` y `_inverse_params`, y
   `_get_readable_fields`.
5. Tres filas de `_ACCESS` y su siembra.

## Controles previstos

- un usuario interno no lee ninguno de los tres;
- `views` de una acción de ventana lee la vista declarada en `view_ids`;
- `params` de `client` devuelve el dict que `params_store` guarda, y
  escribir `params` guarda su `repr`;
- `_get_readable_fields` de `act_url` y `client` incluye los campos de la
  fuente.

Prueba: `tests/unit/base/test_ir_actions_view_url_client_basemodel.py`.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsActWindowView` sobre `models.BaseModel`, campos `view_id` y `act_window_id` en forma C | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:411-425` |
| `IrActionsActWindow.views` sobre el recordset de `view_ids` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:282-296` |
| `IrActionsActUrl` sobre `models.BaseModel` y `IrActionsActUrl._get_readable_fields` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:445-461` |
| `IrActionsClient` sobre `models.BaseModel`; campos `context`, `params` y `params_store`; `IrActionsClient._compute_params`, `IrActionsClient._inverse_params`, `IrActionsClient._get_readable_fields` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:1426-1463` |
| filas `ir_actions_act_window_view_group_system`, `ir_actions_act_url_group_system` e `ir_actions_client all` de `_ACCESS` | `src/addons/base/security/ir_model_access.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:105-110` |
| migración `0143_ir_actions_view_url_client` con `clear_dangling_view_ids`, `context_as_python_literal` y `params_as_python_literal` | `src/addons/base/migrations/0143_ir_actions_view_url_client.py` | ídem |

Prueba: `tests/unit/base/test_ir_actions_view_url_client_basemodel.py`, 11
casos. RED antes del cambio: 11 fallidos.

- El control de `views` pasaba también antes: con `view_id` entero, la
  vista declarada salía con su pk igual. No discriminaba el cambio a
  Many2one; se le añadió la aserción sobre el tipo del campo.
- `create` con `params` no guardaba nada: el paso de inversos de
  `BaseModel.create` llama a `_inverse_params`
  (`src/orm/models.py:1082-1105`), pero asignar el campo de Django en el
  registro no lo persiste. La asignación de la fuente es una escritura en
  su ORM; el inverso escribe con `write`, como `ir_attachment._inverse_raw`
  escribe con `save`.
- `params_store` pasa de `jsonb` a `bytea` con `convert_to(…::text,
  'UTF8')` y después se reescribe con `repr`; `view_id` se vacía donde no
  apunta a una vista antes de añadir la clave foránea.
