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

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrEmbeddedActions` sobre `models.BaseModel` con `_name`, `_description` y `_order`; campos `name`, `sequence`, `parent_action_id`, `parent_res_id`, `parent_res_model`, `action_id`, `python_method`, `user_id`, `is_deletable`, `default_view_mode`, `is_visible`, `domain`, `context`, `groups_ids`; restricciones `ir_embedded_actions_check_only_one_action_defined` e `ir_embedded_actions_check_python_method_requires_name` | `src/addons/base/models/ir_embedded_actions.py` | `odoo19c: odoo/addons/base/models/ir_embedded_actions.py:8-41` |
| `IrEmbeddedActions.create`, `IrEmbeddedActions._compute_display_name`, `IrEmbeddedActions._compute_is_deletable`, `IrEmbeddedActions._compute_is_visible`, `IrEmbeddedActions._unlink_if_action_deletable`, `IrEmbeddedActions._get_readable_fields` | ídem | `odoo19c: odoo/addons/base/models/ir_embedded_actions.py:43-111` |
| `IrActionsActWindow.embedded_action_ids` calculado e `IrActionsActWindow._compute_embedded_actions` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:332,336-339` |
| `IrFilters.embedded_action_id`, su índice `ir_filters_get_filters_index` y su restricción `ir_filters_check_res_id_only_when_embedded_action` | `src/addons/base/models/ir_filters.py` | `odoo19c: odoo/addons/base/models/ir_filters.py:23-36` |
| fila `ir_embedded_actions_group_user` de `_ACCESS` | `src/addons/base/security/ir_model_access.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:109` |
| las dos reglas de `ir.embedded.actions` de `_RULES` | `src/addons/base/security/base_security.py` | `odoo19c: odoo/addons/base/security/base_security.xml:207-227` |
| migración `0144_ir_embedded_actions_basemodel` con `empty_python_method_as_null` y `context_as_python_literal` | `src/addons/base/migrations/0144_ir_embedded_actions_basemodel.py` | ídem y `odoo19c: odoo/orm/fields_relational.py:1291-1295` |

Prueba: `tests/unit/base/test_ir_embedded_actions_basemodel.py`, 13 casos.
RED antes del cambio: 10 fallidos de 12; el caso de `ir.filters` pasaba
porque `get_field` resuelve también el `attname`, y se le añadió la
aserción sobre el nombre y la columna.

- `is_visible` no declara `depends_context` en la fuente: su valor queda en
  la caché del registro. La prueba lee la visibilidad con `active_id` y
  sólo después la invalida antes de leerla con otro registro activo; el
  caso sin `active_id` usa un registro propio.
- `res.partner` no está sobre `models.BaseModel` en este árbol y
  `self.env['res.partner']` no tiene `search`; el modelo padre de las
  pruebas de visibilidad es `ir.filters`, que sí lo está.
- Anulación: sin el filtro por `is_visible` de `_compute_embedded_actions`
  y sin la excepción de `_unlink_if_action_deletable` caen exactamente sus
  dos casos.
- Subconjunto derivado (`grep` de `IrEmbeddedActions`, `embedded_action`,
  `IrFilters`, `act_window`, `base_security`, `seed_base_acl`,
  `ir_model_access` sobre `tests/`, 44 archivos): 674 pasados, 0 fallidos.
