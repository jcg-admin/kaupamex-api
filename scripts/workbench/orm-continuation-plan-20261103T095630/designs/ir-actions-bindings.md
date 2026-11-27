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
