# Porte de ir.filters a 19 sobre BaseModel (ir-filters-port-19-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_filters.py:7-109` — el modelo entero:
  cabecera (`_name`, `_description`, `_order = 'model_id, name, id desc'`),
  diez campos, tres objetos de tabla y siete métodos.
- `odoo19c: odoo/addons/base/security/ir.model.access.csv:114-117` — cuatro
  filas `ir_filters all` (1,1,1,1) para `group_erp_manager`, `group_user`,
  `group_portal` y `group_public`.
- `odoo19c: odoo/addons/base/security/base_security.xml:74-104` — tres reglas:
  `ir.filters.admin.all.rights` (`[(1, '=', 1)]`, `group_erp_manager`),
  `ir.filter: owner or global` (`[('user_ids','in',[False,user.id])]`,
  `group_user`) e `ir.filter: portal/public`
  (`[('user_ids', 'in', user.ids)]`, `group_portal` + `group_public`).
- Consumidor: `odoo19c: addons/web/controllers/json.py:270-277`
  (`get_default_domain` recorre `get_filters` y toma el primero con
  `is_default`).

## Estado heredado (medido)

El porte declara en su docstring que «se porta 18, no 19». Es estado
incorrecto heredado: 19 gobierna. Diferencias medidas contra la fuente:

| Eje | Porte | 19 |
|---|---|---|
| base | `RecordLoaderMixin, Model` | `models.Model` → `BaseModel` |
| cabecera | sin `_name`/`_description`/`_order` | los tres |
| dueño | `user` Many2one nullable (forma 18) | `user_ids` Many2many, vacío = compartido |
| `model_id` | etiqueta de Django (`app_label.ModelName`) | `_name`, vía `_list_all_models` |
| unicidad | `uq_ir_filters_model_user_action_name` (18) | ninguna |
| `save()` | desmarca otros por defecto (`_check_global_default` de 18) | sin esa lógica |
| métodos | `__str__`, `save` | `_list_all_models`, `copy_data`, `write`, `_get_eval_domain`, `_get_action_domain`, `get_filters`, `create_filter` |
| ACL / reglas | ninguna sembrada | 4 filas, 3 reglas |

## Cambio

1. Clase `IrFilters(models.BaseModel)` con `_name`, `_description`, `_order`.
2. `user_ids = fields.Many2many(ResUsers, relation='ir_filters_res_users_rel',
   column1='ir_filters_id', column2='res_users_id')`: la tabla y columnas que
   el ORM de la fuente deriva para `ir.filters` × `res.users`.
3. `model_id = fields.Selection(selection='_list_all_models')` sobre la
   columna de texto; los valores son la identidad de `orm.registry.identity_of`
   (el `_name`, o la etiqueta mientras la clase no declare uno), la misma que
   guarda `ir_model.model` (`designs/model-identity-contract.md`).
4. Los siete métodos de la fuente, con su firma. `_list_all_models` lee
   `ir_model` ordenado por nombre; `write` llama a `check_access('write')`
   tras escribir; `get_filters` hace `search_read` con
   `[('user_ids', 'in', [uid, False])]` y el dominio de acción.
5. Se retira la lógica de 18 de `save()` (el «un solo por defecto») y el
   `UniqueConstraint` de 18. El guardián del cero de
   `embedded_parent_res_id` se lleva a `copy_data`, donde la fuente lo pone
   (`:54-57`); se mide si `create` también lo necesita (el conversor de
   `Integer`) antes de retirarlo de `save()`.
6. Migración de esquema: crea la tabla de relación, copia cada `user_id`
   no nulo a una fila, convierte `model_id` de etiqueta a identidad, y retira
   `user` y la restricción de 18.
7. ACL: las 4 filas entran al volver a ejecutar `probes/derive_base_acl.py`
   una vez que el modelo declara `_name` (la lista no se escribe a mano;
   `src/addons/base/security/ir_model_access.py:23-30`). Reglas (3) en
   `base_security.py`. Una migración de datos siembra las dos cosas en las
   bases que ya pasaron por `0059`.
8. `addons/web/controllers/json.py::get_default_domain` recorre
   `get_filters(identity_of(model), action.pk)` como la fuente.

## Lo que esta unidad no cierra

- El segundo llamador de `get_filters` en la fuente es `get_views`
  (`odoo19c: odoo/addons/base/models/ir_ui_view.py:2970-2973`, opción
  `load_filters`). `get_views` no está portado (0 coincidencias de
  `load_filters`/`def get_views` en `src/`); ese llamador entra con su unidad.
  El plan no la registra hoy: se añade una fila pendiente al incorporar esta.

## Pruebas (por escribir antes del código)

- Cabecera y base; `user_ids` vacío = compartido; la regla de empleado deja
  ver propios y compartidos y no los de otro; la de portal sólo los propios;
  `get_filters` respeta acción y modelo; `create_filter` descarta
  `embedded_parent_res_id` sin acción embebida; `copy_data` añade
  «(copy)» y descarta el cero; `_get_eval_domain` con un dominio inválido
  levanta `ValueError`; `write` sin permiso levanta `AccessError`;
  `get_default_domain` del consumidor web.
- Las pruebas de 18 en `tests/unit/base/test_ir_filters.py` (unicidad del
  por defecto, `user` como FK) cambian de sujeto: 19 no las tiene.

## Adenda: lo que apareció al implementar

- **`res.users.context_get`** era prerrequisito y no estaba portado: unidad
  propia (`designs/res-users-context-get.md`, asentada).
- **`Many2many.read`** como lectura del campo tampoco: `search_read` con
  `user_ids` revienta en `_fetch_query`. Unidad propia en el mismo pase
  (`designs/orm-many2many-field-read.md`).
- **`user.ids`** en la regla de portal: el usuario del contexto de las reglas
  es una fila de Django sin `ids`, y la siembra de reglas fallaba al validar
  el dominio (30 errores en el subconjunto). `ResUsers.ids` lo da como la
  fuente lo da a un registro (`odoo19c: odoo/orm/models.py:5904-5909`).
- `test_domain_in_required::test_the_count_over_a_fixed_population` pasa de
  27 a 28 discrepancias: la nueva es `base.IrFilters.user_ids`, un Many2many
  sin columna propia (medido por sonda). El caso pide re-medir y actualizar con
  su razón; se actualizó así.
- `tests/unit/base/test_ir_filters.py`: los seis casos de la forma de 18
  cambian de sujeto (`user` → `user_ids`; dos por defecto del mismo modelo
  conviven) y escriben con `sudo()`, porque ahora hay ACL.
- `get_default_domain` del consumidor web recorre `get_filters` con la
  identidad del modelo, como la fuente.

## Medido

- `tests/integration/base/test_ir_filters_port_19.py`: 7 casos en rojo antes
  del modelo (`KeyError: 'ir.filters'`, la base no era `BaseModel`).
- Anulación de la regla de empleado (retirada de `_RULES` y su fila): caen
  exactamente los 2 casos que dependen de ella (visibilidad y escritura sobre
  un filtro ajeno). Restaurada con `cmp`.

## Símbolos del cambio, con su cita y su prueba

| Símbolo | Referencia | Prueba |
|---|---|---|
| `IrFilters` (cabecera, campos, `embedded_action`) | `odoo19c: odoo/addons/base/models/ir_filters.py:7-40` (`embedded_action_id`, `:23`) | `tests/integration/base/test_ir_filters_port_19.py`, `tests/unit/base/test_ir_filters.py` |
| `_list_all_models`, `copy_data`, `write`, `_get_eval_domain`, `_get_action_domain`, `get_filters`, `create_filter` | `odoo19c: odoo/addons/base/models/ir_filters.py:42-109` | `tests/integration/base/test_ir_filters_port_19.py` |
| `0131_ir_filters_port_19` (esquema y paso de datos: dueño → `user_ids`, etiqueta → identidad) | `odoo19c: odoo/addons/base/models/ir_filters.py:13` | `tests/unit/base/test_ir_filters.py` |
| `0132_seed_ir_filters_security` (ACL y reglas en bases ya migradas) | `odoo19c: odoo/addons/base/models/ir_filters.py:7-10` y `base_security.xml:74-104` | `tests/integration/base/test_ir_filters_port_19.py` |
| `ResUsers.ids` | `odoo19c: odoo/orm/models.py:5904-5909` | `tests/integration/base/test_ir_filters_port_19.py` (portal) |
| `get_default_domain` | `odoo19c: addons/web/controllers/json.py:270-277` | `tests/integration/base/test_ir_filters_port_19.py` |

`embedded_action` conserva el nombre de su porte anterior (forma B, columna
`embedded_action_id`); sólo cambian su `verbose_name` y su `help_text`, que
pasan al texto de la fuente (`:23`).
