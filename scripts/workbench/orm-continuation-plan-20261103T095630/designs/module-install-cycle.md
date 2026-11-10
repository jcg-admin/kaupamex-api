# Ciclo de instalación: `load_modules` sobre `INSTALLED_APPS` (unidad L)

Diseño escrito antes de tocar código (2026-11-10). Resuelve el paso 0 de la
seguridad de HR (`hr-basemodel-dependencies.md`) y deja sin efecto la tabla
de tres salidas que allí quedó abierta: las tres partían de una premisa
falsa (que la categoría de HR sólo podía venir del XML de datos de `base`).

## Contrato de la referencia

`odoo19c: odoo/modules/loading.py` (rev. `abe4040e`):

1. `load_modules` prepara el grafo de módulos y llama a
   `load_module_graph`.
2. Antes, `ir.module.module.update_list()` registra los módulos del
   `addons_path`; por cada manifiesto, `modules.db.create_categories` crea
   la cadena de categorías de su clave `category` con XML-ID
   `base.module_category_<ruta>` (`odoo/modules/db.py`).
3. `load_module_graph` recorre el grafo en orden topológico y, por módulo
   con operación de instalación o actualización (`:186-260`):
   - `registry.init_models(cr, model_names, {'module': name}, install)`:
     esquema y reflexión en `ir.model*`; `_reflect_models` crea el XML-ID
     `<módulo>.model_<nombre>` de cada modelo cuyo `_module` es el módulo
     (`odoo/addons/base/models/ir_model.py:462-475`, `model_xmlid` `:63`);
   - `load_data(env, idref, 'init'|'update', kind='data', package)`: los
     archivos de `data` del manifiesto, en su orden, por `convert_file`;
   - estado `installed`, `flush_all`, `commit`.

## Estado aquí (medido sobre `b782aecd`)

| Pieza | Dónde | Estado |
|---|---|---|
| `update_list` + `create_categories` | `base/management/commands/update_module_list.py`, `modules/db.py` | portado; nadie lo ejecuta en `migrate` ni en la siembra de pruebas |
| `ModuleGraph`, `build_graph` | `modules/module_graph.py` | portado |
| `Registry.init_models` + `_reflect_all` | `orm/registry.py` | portado; nadie lo llama por módulo |
| `_reflect_models` | `base/models/ir_model.py:795` | sin el bloque de XML-ID (`:462-475` de la fuente) |
| `load_data`, `convert_file`, `XmlImport` | `modules/loading.py`, `tools/convert.py` | portados; ningún llamador |
| orquestador `load_modules`/`load_module_graph` | — | **falta** (TASK-API-0382) |

La base de pruebas tiene 0 filas en `ir_module_module` y 0 XML-ID `model_*`.

Medición exploratoria (`probe_cycle.py`, transacción revertida):
`update_module_list` registra 124 módulos y crea 39 categorías, entre ellas
`base.module_category_human_resources`; `init_models` termina para `hr` (8
modelos) y `hr_skills` (7) y falla para `base` con
`ValidationError` en la reflexión de la selección de
`res.partner.bank.acc_type`; tras `init_models` hay 0 XML-ID `model_*`.

## Decisión

- **Categorías: TRAE.** `create_categories` dentro de `update_list` ya
  produce `base.module_category_human_resources`; el XML de categorías de
  `base` no hace falta para HR y no se vendoriza en esta unidad.
- **Instalación: CONSTRUYE** en el propietario canónico,
  `modules/loading.py`: `load_modules(using)` recorre el grafo de los
  addons de `INSTALLED_APPS` y por módulo ejecuta `init_models` con
  `{'module': name}` y `load_data` de su clave `data`, y lo marca
  `installed`. El catálogo lo refresca la misma lógica de
  `update_module_list`, que se mueve a una función reutilizable sin
  duplicarla.
- **Cuándo corre:** la señal `post_migrate` de Django, una vez por
  `migrate` y por alias (receptor de `base`, `sender` = su `AppConfig`). Es
  el punto «esquema del módulo al día» del stack —Django crea ahí permisos y
  content types— y llega después de todas las migraciones, así que
  `init_models` y `XmlImport` trabajan con los modelos vivos sobre el
  esquema que declaran. La siembra de pruebas (`tests/conftest.py`,
  `_SEEDERS`) lo llama también, porque `--reuse-db` no ejecuta `migrate`.
- **Divergencia declarada:** «instalar» aquí es estar en `INSTALLED_APPS`
  y migrado; el ciclo no instala por petición (`Registry.new` sigue
  rechazándolas, TASK-API-0382 conserva ese alcance).
- **Sin segundo cargador:** los datos de seguridad de `hr` y `hr_skills`
  entran por su manifiesto (`data`) y `load_data`; no por una migración ni
  por SQL.

## Subunidades, en orden

| # | Qué | Prueba RED | Control |
|---|---|---|---|
| L1 | bloque de XML-ID de `_reflect_models` | tras reflejar con `{'module': 'hr'}` existe `hr.model_hr_employee` apuntando a la fila | retirar el bloque: cae exactamente esa |
| L2 | reflexión de `base` sin el `ValidationError` de `acc_type` | `init_models` de `base` termina | reponer la causa |
| L3 | `load_modules(using)` + `post_migrate` + siembra | tras `load_modules`, todos los addons instalados quedan `installed`, `hr.model_hr_employee` existe y un archivo de `data` declarado se carga una sola vez aunque se ejecute dos veces | quitar la llamada a `load_data`: caen las de datos |
| L4 | `hr/security/hr_security.xml` e `ir.model.access.csv`, `hr_skills/security/*` vendorizados en su manifiesto | `hr.group_hr_user` existe, implica `base.group_user`, cuelga de `hr.res_groups_privilege_employees` | quitar el archivo del manifiesto |
| L5 | pruebas por privilegio sobre los modelos del grupo A | superusuario, empleado (`base.group_user`), `group_hr_user`, `group_hr_manager`, sin grupo; CRUD y reglas | retirar la fila de `base.group_user` hace caer la lectura del empleado |

Divergencia de datos ya registrada que L4 hereda: `group_hr_manager.user_ids`
enlaza `base.user_root`/`base.user_admin`, que este árbol no siembra
(`res_groups_data.py`, decisión 3). La línea se omite del archivo vendorizado
con un comentario que lo cita; las filas del CSV cuyo modelo no existe aquí
se omiten igual que en `base/security/ir_model_access.py`, y el archivo
declara cuántas y cuáles.

## Ciega a

La conducta de `update`/`upgrade` de un módulo ya instalado (versión,
migraciones `pre`/`post` de Odoo, desinstalación): fuera de esta unidad.

## L1 — implementación (2026-11-10)

`IrModel._reflect_models(app_labels, module=None)` llama al final a
`_update_model_xmlids(module, classes)`, que escribe `<módulo>.model_<nombre>`
por `IrModelData._update_xmlids` para cada modelo cuya app es el módulo y que
declara **su propio** `_name`. `Registry._reflect_all` le pasa
`context.get('module')`. Sin módulo no escribe nada, como la fuente.

Hallazgo de la implementación: el primer intento chocó en
`ON CONFLICT DO UPDATE command cannot affect row a second time`. Dos modelos
de `hr` (`HrDepartment`, `HrJob`) no declaraban `_name` y heredaban
`'mail.thread'` del mixin. Medido en todo el árbol: **12** modelos concretos
con `_name` heredado (`fleet` ×4, `hr` ×2, `analytic`, `base_automation`,
`mass_mailing`, `stock.ReturnRequest`, `helpdesk.SupportTicket`,
`website.StaticPage`). Por eso el filtro es `'_name' in vars(model)`, y los
dos de `hr` reciben sus atributos de clase de la referencia (`_name`,
`_description`, `_inherit`; `_order` en el departamento), con los que
dependen de campos no portados declarados como pendientes en su docstring.
`makemigrations hr --check`: sin cambios.

Prueba: `tests/unit/base/test_reflect_models_xmlids.py` (4 casos; RED 3 de 4).
Controles: sin la llamada caen exactamente 2
(`test_the_module_models_get_their_xmlid`,
`test_only_the_models_with_a_reference_name_get_an_xmlid`); sin el filtro de
dueño cae exactamente 1 (`test_a_model_of_another_module_is_not_named_by_this_one`).
Subconjunto derivado (`grep -rlE "_reflect_models|_reflect_all|init_models|
hr\.department|hr\.job|HrDepartment|HrJob|..." tests/`, 9 directorios):
**6189 passed, 65 skipped, 0 failed**.

## L2 — implementación (2026-11-10)

La medición sobre los 124 módulos en orden de grafo (`probe_cycle.py`,
transacción revertida) encontró tres fallos de `init_models`, y los tres
eran divergencias con la referencia:

| Fallo | Referencia | Corrección |
|---|---|---|
| `_reflect_selections` rechaza `res.partner.bank.acc_type` (etiquetas perezosas) | sólo refleja `if isinstance(field.selection, list)` (`ir_model.py:1547`); una selección invocable se salta | `if not isinstance(choices, (list, tuple))`: la invocable de Django (`CallableChoiceIterator`) se salta |
| `check_indexes`: `'One2many' object has no attribute 'concrete'`, y `IrModelInherit` sin `_fields` | `Model._fields` + `field.column_type and field.store` (`registry.py:813-814`) | `model_field_registry(model)` (el registro de campos legible por la clase, también la de Django) y `getattr(field, 'concrete', False)` |
| `_reflect_model_params` de `product.removal`: `Meta.ordering` con `OrderBy` | `'order': model._order`, siempre texto (`ir_model.py:430`) | `_ordering_text`: cada término a su texto (`name`, `name desc`) |

Tras las tres, `init_models` termina para los 124 módulos y escribe 205
XML-ID `model_*`.

Pruebas nuevas: `test_reflect_selections_callable.py` (2),
`test_reflect_model_params_ordering.py` (2), y dos casos en
`test_index_method.py`. Controles: quitar el salto de la invocable cae
exactamente `test_a_callable_selection_is_left_out`; volver a `_fields` cae
exactamente el caso del modelo de Django; volver a `field.concrete` cae
exactamente el del `One2many` declarado; el RED de la traducción del orden
fue `TypeError: expected str instance, OrderBy found`.

`test_registry_schema_axis.py` usa dobles de modelo: su `_Meta` expone ahora
`get_fields()` y `private_fields`, la interfaz que `model_field_registry` lee
de un modelo real.

Subconjunto derivado (`grep -rlE "check_indexes|_reflect_selections|
_reflect_model_params|_reflect_models|init_models|IrModelFieldsSelection"
tests/`, 6 directorios): **7570 passed, 65 skipped, 6 xfailed, 0 failed**.

## L3 — implementación (2026-11-10)

- `modules.loading.load_modules(using)`: `update_module_list` (catálogo y
  `create_categories`), grafo `ModuleGraph.from_database(..., mode='update')`
  sobre `installed_addon_names()` (el modo `load` de la fuente descarta los no
  instalados), y por módulo `init_models(..., {'module': name}, install)`,
  `load_data({}, 'init'|'update', 'data', package, using)` y estado
  `installed`; al final `flush_all`, dentro de un `Environment` de
  superusuario.
- `installed_addon_names` pasa a `modules/module.py` (descubrimiento de
  addons); `update_module_list` lo importa de allí: `modules` no importa
  `addons`.
- Receptor `addons/base/install_cycle.load_modules_after_migrate`, conectado
  en `BaseConfig.ready()` con `importlib.import_module` (excepción #4 de
  `no-lazy-imports.md`: el módulo importa `modules.loading`, que define
  modelos). Guardas de `create_permissions`: sólo con `plan` (`migrate` lo
  pasa; `flush` no) y sólo donde el router migra `base`.
- Siembra de pruebas: `_install_modules` al final de `_SEEDERS`, porque tras
  un `flush` el receptor no actúa.

Observación de camino real: `create_test_db(keepdb=True)` ejecuta `migrate`
también con `--reuse-db`, así que la base de pruebas quedó con los 124 módulos
`installed` y 205 XML-ID `model_*` por el propio receptor, sin la siembra.

Consecuencia para las pruebas: las que construían su catálogo (`base`,
`sale`…) o sus filas reflejadas suponían tablas vacías. Se les da
`empty_module_catalog` (fixture de `tests/conftest.py` que vacía el catálogo
dentro de la transacción) o parten sin los XML-ID/restricciones que el ciclo
crea; `test_fk_three_axes` vacía la caché de la transacción, porque la fila de
`ir.model` que mide ya existe y leerla la deja en caché.

Prueba: `tests/integration/base/test_load_modules.py` (5 casos). Controles:
sin `init_models` cae `test_the_models_get_their_module_xmlid`; sin `load_data`
cae `test_the_data_files_load_in_graph_order`; sin el estado caen
`test_every_installed_addon_ends_installed` y la de orden (su segunda pasada
espera `update`); sin la guarda de `plan` cae
`test_migrate_runs_the_cycle_and_flush_does_not`.

Primer gate completo: 5 failed, 21 errors, todos de pruebas que suponían el
catálogo vacío (`base_install_request` 19, `test_fk_three_axes` 1,
`test_sql_error_to_message` 1) — corregidos como arriba.

Gate completo de la forma final: **12 628 passed, 66 skipped, 6 xfailed,
0 failed, 5 errors** en 540 s (los 5 de `test_multidb_isolation.py`).

## L4 — medición previa (2026-11-10)

**ACL.** Filas de `ir.model.access.csv` cuyo `model_id:id` resuelve a un
modelo reflejado aquí (medido contra los XML-ID `model_*` que deja L3):
`hr` 18 de 26 y `hr_skills` 13 de 20. Las demás nombran modelos no
portados: asistentes (`hr.departure.wizard`, `hr.version.wizard`,
`hr.bank.account.allocation.wizard[_line]`, `hr.employee.cv.wizard`),
informes (`hr.employee.skill.report`, `…certification_report`,
`…skill.history.report`), `resource.resource`, `resource.calendar[_attendance]`
y `mail.activity.plan[_template]`. Se vendorizan los dos CSV sin esas filas y
el archivo declara cuáles faltan y por qué, como
`base/security/ir_model_access.py`.

**Reglas.** Rutas de dominio resueltas contra `model_field_registry`
(`probe_rule_paths.py`):

| Regla | Ruta que falta | Qué la cierra |
|---|---|---|
| `hr.hr_employee_comp_rule` | `hr.employee.user_id` | portar `user_id` como en la fuente: Many2one relacionado y almacenado (`related='resource_id.user_id'`, `store=True`, `ondelete='restrict'`, `index='btree_not_null'`); hoy es una `property` |
| `hr_skills.hr_skills_rule_employee_update` | `hr.employee.user_id` | ídem |
| `hr_skills.hr_skill_rule_employee_update` | `hr.employee.user_id` | ídem |
| `hr.ir_rule_res_partner_bank_internal_users` | `res.partner.employee_ids` | el One2many de `hr/models/res_partner.py:11` (inverso de `work_contact_id`) |
| `hr.ir_rule_hr_departure_reason_multi_company` | `hr.departure.reason.country_code` | `related='country_id.code'` (`hr_departure_reason.py:15`) |

Las reglas de `mail.activity.plan*` y de los tres informes de `hr_skills`
quedan fuera con su modelo. Las demás resuelven.

Consecuencia de orden: L4 empieza por `hr.employee.user_id` (campo, migración
y valor en las filas existentes, que es el contrato de los calculados
almacenados), sigue con `res.partner.employee_ids` y `country_code`, y sólo
entonces carga los dos archivos de seguridad por el manifiesto.

### L4a — `hr.employee.user_id` (diseño)

Referencia (`odoo19c: addons/hr/models/hr_employee.py:86-94`):
`user_id = fields.Many2one('res.users', 'User', related='resource_id.user_id',
store=True, readonly=False, check_company=True, precompute=True,
index='btree_not_null', ondelete='restrict')`.

Aquí `hr.employee` no deriva de `BaseModel`: es un modelo de Django con
`ResourceMixin`, que ya sincroniza en `save()` los otros dos relacionados
almacenados del recurso (`company_id`, `resource_calendar_id`; divergencia 2
de `hr_employee.py`), y `user` es hoy una `property` de sólo lectura sobre
`resource.user` (23 consumidores medidos con
`grep -rn "employee\.user\b|resource__user|…" addons src`).

Forma: el campo se declara como columna (`user_id`, columna `user_id`, FK a
`res.users`, `on_delete=PROTECT` ≙ `ondelete='restrict'`, índice parcial
`IS NOT NULL` ≙ `btree_not_null`) con el mismo mecanismo de sincronía del
mixin, en los dos sentidos que da `readonly=False` en la fuente: al guardar,
un valor asignado al empleado se escribe en su recurso y, si no se asignó, el
empleado toma el del recurso. La migración añade la columna y la rellena desde
`resource.user_id` en las filas existentes (`RunPython`, mismo papel que
`ComputeStoredFields` para un calculado). La `property` desaparece y los
consumidores leen el campo.

Corrección al implementar: la primera versión declaró `user` (attname
`user_id`) y el gate de ADR-029 (`scripts/check_fk_naming.py`) la rechazó: una
FK nueva lleva la forma C, el símbolo fiel `user_id` con `db_column='user_id'`
(attname `user_id_id`), como `hr_employee_public.employee_id`. Los consumidores
de la `property` pasan a `employee.user_id` (siete lecturas en `hr`, `hr_fleet`
y `mail_activity_plan_template`); los filtros por `resource__user` se
conservan porque `save()` iguala las dos columnas. `_user_uniq` sigue
pendiente: es un objeto de tabla y va con la unidad de `_table_objects`.

Pruebas: la columna existe y su valor sigue al recurso al crear; asignar el
usuario en el empleado lo escribe en el recurso; la migración rellena una fila
previa; la regla `hr_employee_comp_rule` resuelve `user_id`. Control: sin la
sincronía cae el caso de creación.
