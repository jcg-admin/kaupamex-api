# ir.actions.actions y act_window_close sobre BaseModel (paso 4a)

TASK-API-0397. Unidad: `ir-actions-actions-basemodel-0397`
(depende de `ir-embedded-actions-basemodel-0397`).

## Referencia (odoo19c, odoo-tools@bf077302)

`odoo/addons/base/models/ir_actions.py`:

- `ir.actions.actions` (`:55-259`): `_name`, `_description='Actions'`,
  `_table='ir_actions'`, `_order='name, id'`, `_allow_sudo_commands=False`;
  `_path_unique` (`:62-65`); `name` Char required translate, `type`,
  `xml_id` calculado (`_compute_xml_id`, `:105-108`), `path`, `help`,
  `binding_type`, `binding_view_types`; `create` y `write` limpian la caché
  del registro (`:110-121`); `unlink` borra los `ir.actions.todo` y los
  `ir.filters` (con `active_test=False`) de las acciones y limpia la caché
  (`:123-133`); `_get_action_dict` arma el diccionario con
  `self.sudo().read()[0]` filtrado por `_get_readable_fields`
  (`:236-245`).
- `ir.actions.act_window_close` (`:428-443`): `_name`, `_description`,
  `_inherit=['ir.actions.actions']`, `_table='ir_actions'`,
  `_allow_sudo_commands=False`, `type` con default
  `'ir.actions.act_window_close'`, y `_get_readable_fields` con `effect` e
  `infos`.
- `ir.actions.act_window._get_action_dict` (`:388-397`): lee los
  `embedded_action_ids` del diccionario con los campos legibles de
  `ir.embedded.actions`.

`security/ir.model.access.csv:100,102`: `ir_actions_group_system` y
`ir_actions_act_window_close_group_system`, `group_system` 1,1,1,1.

## Estado del árbol (medido)

- `IrActionsActions` (`src/addons/base/models/ir_actions.py:461`) es un
  modelo Django sin `_name` ni métodos propios; `IrActionsActWindowClose`
  es un proxy de Django que fija `type` en `save()`.
- `IrActionsBase._get_action_dict` (`:376-393`) recorre `_meta.fields`,
  que no contiene los calculados no almacenados: `embedded_action_ids` del
  paso 3d no sale en el diccionario.
- `_ACCESS` no tiene fila para ninguno de los dos modelos.
- `_check_path` vive en `IrActionsBase.clean()` y no comprueba la unicidad
  entre las tablas heredadas (`:94-104` de la fuente).

## Cambio

1. `IrActionsActions(models.BaseModel, IrActionsBase)` con los atributos;
   `create`, `write`, `unlink`, `_compute_xml_id` y `xml_id`.
2. `IrActionsActWindowClose(models.BaseModel, IrActionsBase)` sobre la
   tabla `ir_actions` con su `type` por defecto y `_get_readable_fields`.
3. `_get_action_dict` de la base con `read()`, y el de `act_window`.
4. Las dos filas de ACL.

## Lo que esta unidad no cierra

- `binding_model_id` (Many2one a `ir.model`) sustituye a
  `binding_model_name`, y `get_bindings`/`_get_bindings`: unidad 4c.
- `res.users.action_id`, `_check_action_id` y `_unlink_check_home_action`:
  unidad 4b.
