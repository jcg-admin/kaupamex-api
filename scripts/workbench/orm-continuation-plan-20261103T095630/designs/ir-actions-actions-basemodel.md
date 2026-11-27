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

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsBase` sobre `models.Model` (sin `DefaultGetMixin`, `CopyMixin`, `OriginMixin` ni `TimeStampedModel`), con `xml_id`, `_compute_xml_id`, `create`, `write`, `unlink` y `_get_action_dict` con `read()` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:55-133,236-245` |
| `IrActionsActions` sobre `models.BaseModel` con `_name`, `_description`, `_table`, `_order`, `_allow_sudo_commands` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:55-60` |
| `IrActionsActWindowClose` concreto con `managed = False` sobre `ir_actions`, `type` con su valor por defecto e `IrActionsActWindowClose._get_readable_fields` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:428-443` |
| `IrActionsActWindow._get_action_dict` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:388-397` |
| bases `(IrActionsBase, models.BaseModel, TimeStampedModel)` de `IrActionsActWindow`, `IrActionsActUrl`, `IrActionsClient`, `IrActionsServer` e `IrActionsReport` | `src/addons/base/models/ir_actions.py`, `src/addons/base/models/ir_actions_report.py` | el `_inherit = ['ir.actions.actions']` de cada subtipo (`ir_actions.py:265,431,449,589,1429`; `ir_actions_report.py:160`) |
| `EmptyListHelpMixin.get_empty_list_help` como `classmethod`, en las bases de `BaseModel` y de `TimeStampedModel` | `src/orm/models.py`, `src/addons/base/models/timestamped_mixin.py` | `odoo19c: odoo/addons/base/models/ir_ui_view.py:2747-2758` |
| `models.ManyToOneRel.convert_to_read` | `src/orm/fields_relational.py` | `odoo19c: odoo/orm/fields_relational.py:668-669` |
| filas `ir_actions_group_system` e `ir_actions_act_window_close_group_system` de `_ACCESS` | `src/addons/base/security/ir_model_access.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:100,102` |
| migración `0145_ir_actions_actions_basemodel` | `src/addons/base/migrations/0145_ir_actions_actions_basemodel.py` | ídem |

Prueba: `tests/unit/base/test_ir_actions_actions_basemodel.py`, 11 casos.
RED antes del cambio: 11 fallidos.

- **El orden de las bases.** Medido sobre `IrActionsServer.__mro__`:
  `IrActionsServer, BaseModel, IrActionsBase, DefaultGetMixin, …`, con
  `unlink` y `copy` definidos en `BaseModel`. Un `create`/`write`/`unlink`
  en `IrActionsBase` no se alcanzaba. Con `IrActionsBase` delante, la
  llamada `act_window.unlink` → `IrActionsBase.unlink` → `BaseModel.unlink`
  es la de la fuente. `IrActionsBase` deja los tres mixins porque, tras
  esta unidad, todo subtipo es `models.BaseModel`, que ya los trae.
- **`act_window_close`.** Un `proxy` de Django no admite redeclarar `type`;
  un modelo concreto con `managed = False` sobre `ir_actions` sí, y Django
  no crea ni migra la tabla. `registry.is_not_null` descarta todo modelo
  no gestionado (`src/orm/registry.py:1742`), así que sus nueve campos con
  columna suben el recuento fechado de `test_domain_in_required.py` de 28 a
  37; el optimizador sólo deja de recortar el `False`, que es la respuesta
  conservadora.
- **`read()` sin campos** recorre `fields_get`, que lista las relaciones
  inversas de Django (`todos`, `filter_ids`, `view_ids`, …); ninguna tenía
  `convert_to_read`. La fuente se lo da a todo `One2many` por
  `_RelationalMulti`; aquí se cuelga de `ManyToOneRel` como ya se cuelgan
  `convert_to_cache` y `convert_to_write`.
- **`get_empty_list_help`** estaba sólo en `BaseModel` (paso 3b): leer una
  acción de ventana sobre `res.partner`, que no es `BaseModel`, fallaba al
  llamarlo. La fuente lo declara con `@api.model` en el modelo `base`; aquí
  viaja como `BaseUrlMixin`, por `BaseModel` y por `TimeStampedModel`, como
  `classmethod`.
- **La prueba de `unlink`** borraba primero un `ir.actions.actions`: ahí la
  cascada de Django ya se lleva los filtros, y la anulación del borrado
  explícito no caía. Sobre una acción de ventana la cascada no llega, que es
  el caso del comentario de la fuente; anulado el borrado, cae ese caso.
- Anulación: sin `clear_cache` en `write`, sin el borrado de `ir.filters` en
  `unlink` y sin `ManyToOneRel.convert_to_read` caen exactamente los cuatro
  casos que dependen de ellos.
- Subconjunto derivado (`grep` de `IrActions`, `ir.actions`, `act_window`,
  `_get_action_dict`, `_for_xml_id`, `get_empty_list_help`, `.read(`,
  `fields_get`, `IrEmbeddedActions`, `IrFilters`, `TimeStampedModel` sobre
  `tests/`, 99 archivos): 1459 pasados y 2 fallidos, los dos corregidos
  arriba (`action_id` vacío es un recordset; el recuento fechado).
