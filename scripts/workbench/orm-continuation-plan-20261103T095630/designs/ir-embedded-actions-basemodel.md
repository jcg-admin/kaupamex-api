# ir.embedded.actions sobre BaseModel y act_window.embedded_action_ids calculado (paso 3d)

TASK-API-0397. Unidad: `ir-embedded-actions-basemodel-0397`
(depende de `ir-actions-view-url-client-basemodel-0397`).

## Referencia (odoo19c, odoo-tools@bf077302)

`odoo/addons/base/models/ir_embedded_actions.py:8-111`:

- atributos: `_name='ir.embedded.actions'`, `_description='Embedded Actions'`,
  `_order='sequence, id'` (`:9-11`);
- campos (`:13-29`): `name` Char translate, `sequence`, `parent_action_id`
  M2o `ir.actions.act_window` required cascade, `parent_res_id` Integer,
  `parent_res_model` Char required, `action_id` M2o `ir.actions.actions`
  cascade, `python_method` Char, `user_id` M2o `res.users` cascade,
  `is_deletable` calculado, `default_view_mode`, `filter_ids` O2m
  `ir.filters.embedded_action_id`, `is_visible` calculado, `domain` default
  `'[]'`, `context` default `'{}'`, `groups_ids` M2m `res.groups`;
- dos `models.Constraint` con `IS NULL` / `IS NOT NULL` sobre `action_id` y
  `python_method` (`:31-41`);
- `create` (`:43-55`), `_compute_display_name` (`:57-64`),
  `_compute_is_deletable` por `_get_external_ids` y prefijos `__export__`,
  `__custom__` (`:66-73`), `_compute_is_visible` (`:75-96`),
  `_unlink_if_action_deletable` con `@api.ondelete(at_uninstall=False)`
  (`:98-103`), `_get_readable_fields` (`:105-111`).

Tabla del M2m `groups_ids`: sin `relation`, la fuente la deriva
(`odoo/orm/fields_relational.py:1291-1295`): `'%s_%s_rel' % sorted tables`
→ `ir_embedded_actions_res_groups_rel`, columnas `ir_embedded_actions_id`,
`res_groups_id`.

`ir_filters.py:23`: el campo de `ir.filters` es `embedded_action_id`.

`ir_actions.py:332,336-339`: `embedded_action_ids` de `ir.actions.act_window`
es un `One2many` CALCULADO por `_compute_embedded_actions` (busca por
`parent_action_id in self.ids` y filtra por `is_visible`), no un inverso.

ACL: `ir.model.access.csv:109` `ir_embedded_actions_group_user`, group_user
1,1,1,1. Reglas: `base_security.xml:208-227`, dos `ir.rule` (`user_id in
[user.id, False]` para group_user; `(1,'=',1)` para group_system), las dos con
`perm_read=False`, `perm_create=False`.

## Estado del árbol (medido)

`src/addons/base/models/ir_embedded_actions.py`: `TimeStampedModel` plano,
campos `parent_action`, `action`, `user`, `groups` (nombres propios),
`context` Json, `python_method` `''` en vez de NULL, booleano `system` que la
fuente no declara, y métodos propios `disambiguate`, `clean`,
`check_deletable`, `is_visible(...)` con firma inventada. Medido: ningún
consumidor de esos métodos ni de `system` fuera del archivo (grep sobre
src, addons, tests). `ir.filters` declara `embedded_action` (`ir_filters.py:102`).
No hay ACL ni regla de `ir.embedded.actions` en `ir_model_access.py` ni en
`base_security.py`.

## Cambio

1. `IrEmbeddedActions(models.BaseModel, TimeStampedModel)` con los atributos,
   los campos con los nombres de la fuente (forma C, `db_column` igual al
   nombre), `python_method` NULL, `context` Char `'{}'`, `groups_ids` con la
   tabla y columnas derivadas por la fuente, `is_deletable` e `is_visible`
   calculados, `filter_ids` como inverso de `ir.filters.embedded_action_id`;
   los métodos de la fuente; se retiran `system`, `disambiguate`, `clean`,
   `check_deletable` y el método `is_visible`.
2. `ir.filters.embedded_action` → `embedded_action_id`.
3. `IrActionsActWindow.embedded_action_ids` calculado y
   `_compute_embedded_actions`; el FK `parent_action_id` pasa a
   `related_name='+'`.
4. ACL y las dos reglas.
5. Migración: renombres de estado (columnas iguales), tabla y columnas del
   M2m, `''`→NULL en `python_method` antes de las nuevas restricciones,
   `context` JSON → literal Python, retiro de `system`, ACL y reglas.

## Lo que esta unidad no cierra

`_get_action_dict` de `act_window` (`ir_actions.py:388-397`) necesita que el
`_get_action_dict` base lea con `self.sudo().read()[0]` (`:236-245`), y el
árbol arma el diccionario recorriendo `_meta.fields`, que no contiene un
calculado no almacenado. `IrActionsActions` todavía no es `BaseModel`, así
que no tiene `read`. Se porta en el paso 4, junto con `ir.actions.actions`.
