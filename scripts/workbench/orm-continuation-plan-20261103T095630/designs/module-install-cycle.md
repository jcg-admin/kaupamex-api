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

### L4b — `res.partner.employee_ids` y `hr.departure.reason.country_code` (diseño)

Las dos rutas que faltaban en las reglas de `hr_security.xml`
(`odoo19c: addons/hr/security/hr_security.xml:64-66,100-101`):

```
[('partner_id.employee_ids', '=', False)]                         res.partner.bank
[('country_code', 'in', user.env.companies.mapped('country_code') + [False])]
```

**`employee_ids`.** La fuente lo declara en `hr/models/res_partner.py:11-13`
como `One2many('hr.employee', 'work_contact_id')`. Aquí el reverso ya existe
y es el de `HrEmployee.work_contact`, pero con `related_name=
'employee_work_contacts'`: el nombre no es el de la fuente y
`model_field_registry(ResPartner)` no responde a `employee_ids`. TRAE: el
reverso de Django es el One2many; se le da el nombre de la fuente
(`related_name='employee_ids'`) y los nueve lectores pasan a él. No cambia el
esquema; la migración es de estado (`AlterField`). En `res.users` el
`employee_ids` propio (el de `user_id`, L4a) tapa al delegado del partner,
igual que en la fuente, donde `hr/models/res_users.py` lo redeclara.

**`country_code`.** La fuente: `fields.Char(related='country_id.code')`, no
almacenado. Aquí es una `property`, invisible para el dominio. TRAE: el campo
relacionado no almacenado del ORM (`Field.setup_related`,
`_search_related` instalado desde `orm/domains.py`), con el texto de la
fuente; el precedente es `ResCompany.country_code`
(`src/addons/base/models/res_company.py:634`). La lectura del registro no
cambia (`''` sin país).

Pruebas: `ResPartner._fields['employee_ids']` existe y es el reverso de
`work_contact`; un dominio `[('partner_id.employee_ids', '=', False)]` sobre
`res.partner.bank` separa la cuenta de un empleado de otra; `country_code`
está en `_fields` y `search([('country_code', 'in', ['MX', False])])` filtra
por el código del país. Control: con el nombre viejo cae el caso del dominio
de cuentas; con la `property` cae el de `country_code`.

### L4c — datos de seguridad de `hr` y `hr_skills` por el manifiesto (diseño)

Fuente: `odoo19c: addons/hr/security/{hr_security.xml,ir.model.access.csv}`
y `addons/hr_skills/security/{hr_skills_security.xml,ir.model.access.csv}`,
declarados en la clave `data` de cada manifiesto. Licencia LGPL-3: se copian
y se adaptan, con atribución.

**Conducta medida hoy.** `IrModelAccess.check` (`ir_model.py`, `check`)
niega si el modelo no está en `_get_allowed_models`: sin filas de ACL un
usuario que no es superusuario no lee ningún modelo de `hr`. Las pruebas de
L4a lo mostraron (`PermissionDenied` al guardar sin `sudo`). Cargar los
archivos es lo que da acceso a `base.group_user`, `hr.group_hr_user` y
`hr.group_hr_manager`; no hay que elevar nada.

**Resolución medida** contra los XML-ID que dejan L1–L3 (corrige las cifras
de L4, que eran 18 y 13):

| Archivo | Filas | Resuelven | Faltan y por qué |
|---|---|---|---|
| `hr/ir.model.access.csv` | 26 | 16 → **20** | 4 `resource.model_*`: los modelos de `resource` no declaran `_name` (se portan, ver abajo); 4 asistentes (`hr.departure.wizard`, `hr.version.wizard`, `hr.bank.account.allocation.wizard[_line]`): son modelos abstractos de Django, sin tabla ni fila en `ir.model`; 2 de `mail.activity.plan[_template]`: modelo no portado |
| `hr_skills/ir.model.access.csv` | 20 | **14** | 5 de los tres informes y 1 del asistente de CV: modelos no portados |

**`_name` de `resource`.** `ResourceResource`, `ResourceCalendar`,
`ResourceCalendarAttendance` y `ResourceCalendarLeaves` no declaran los
atributos de clase que la fuente declara (`resource/models/*.py`): se portan
`_name`, `_description` y `_order` donde la fuente los tiene
(`atributos-de-clase-de-modelo.md`). Con eso `resource.model_resource_*`
existe y las cuatro filas de ACL resuelven. `db_table` ya coincide con el
nombre.

**Omisiones en el XML, declaradas en el propio archivo:**

- `group_hr_manager.user_ids` (`base.user_root`, `base.user_admin`): esos
  usuarios no existen en este árbol; los usuarios se crean por configuración.
- `mail_plan_rule_group_hr_manager` y `mail_plan_templates_rule_group_hr_manager`:
  modelo no portado.
- En `hr_skills`, las cinco reglas de los tres informes.

El resto se copia con su `noupdate`. Las rutas de dominio que nombran ya
resuelven tras L4a y L4b.

**Carga.** `'data': ['security/hr_security.xml', 'security/ir.model.access.csv']`
en `addons/hr/__manifest__.py` (y su par en `hr_skills`); los lee `load_data`
dentro de `load_modules` (L3). Sin migración, sin SQL, sin segundo cargador.

Pruebas: tras `load_modules`, `hr.group_hr_user` existe, implica
`base.group_user` y cuelga de `hr.res_groups_privilege_employees`;
`hr.group_hr_manager` implica `hr.group_hr_user`; hay 20 filas de ACL de
`hr` y 14 de `hr_skills` con el grupo de la fuente; las reglas
`hr_employee_comp_rule` y `ir_rule_res_partner_bank_internal_users` existen
con su dominio. Control: quitar el archivo del manifiesto hace caer
exactamente esas pruebas. El acceso por privilegio lo mide L5.

#### L4c — lo que destapó la carga real (2026-11-10)

Cargar `hr_security.xml` por `load_data` encontró, en orden, cinco huecos
del contrato que cualquier archivo de datos de seguridad necesita:

1. **`res.groups.privilege` sin `_name`.** El cargador no podía nombrar el
   modelo del primer registro. Se portan `_name`, `_description` y `_order`
   (`odoo19c: odoo/addons/base/models/res_groups_privilege.py:5-7`).
2. **`_load_records_create` no aplicaba comandos x2many.** La fuente crea
   con `self.create(vals_list)`, que interpreta los triples de `Command` del
   lado directo de un `Many2many`; aquí `_load_records_write` ya lo hacía y
   `_load_records_create` asignaba la lista sobre el manager de Django.
   Se aparta el lado directo y se aplica tras guardar con
   `apply_many2many_commands`.
3. **Comandos cortos.** `is_command_list` exigía tres elementos; la fuente
   lee por índice y sus datos escriben `(4, id)`, `(3, id)` y `(5,)`. Se
   admiten de uno a tres elementos y `command_triples` los completa en los
   tres recorridos que desempaquetan.
4. **Instalación no atómica.** Un registro que falló dejó en la base de
   pruebas el grupo `Administrator` sin XML-ID (fila 3745, creada a las
   18:46:20 por este trabajo y retirada a mano). La fuente confirma tras
   cargar cada módulo y revierte el que falla; `load_modules` envuelve cada
   paquete en `transaction.atomic(using)` y vuelca el entorno dentro.
5. **`ir.rule.model_id` y `ir.rule.global`.** Ver L4d.

Mientras L4d no esté, la clave `data` de los dos manifiestos no se activa:
con ella la siembra de la sesión de pruebas falla en la primera regla.

### L4d — `ir.rule.model_id` y `ir.rule.global` (diseño)

Fuente (`odoo19c: odoo/addons/base/models/ir_rule.py`): `model_id =
fields.Many2one('ir.model', required=True, index=True, ondelete='cascade')`
y `global = fields.Boolean(compute='_compute_global', store=True)`. Aquí
`model_id` es la divergencia declarada `model_name` (texto, tarea #139) y
`global` la `property` `global_`. Los archivos de datos de la fuente nombran
el modelo por `model_id ref="model_..."` y la regla de estructuras salariales
escribe `global`.

Medición: `IrModel.model` guarda el mismo texto que `IrRule.model_name`
(la etiqueta de Django, p. ej. `hr.HrEmployee`), 58 lecturas de
`model_name` sobre reglas y 23 `IrRule.objects.*` en `src`, `addons` y
`tests`.

Forma: `model_id` como FK a `IrModel` en forma C (`on_delete=CASCADE`,
`db_index`), y `model_name` conservado como columna que `save()` mantiene
igual a `model_id.model` en los dos sentidos —como `HrEmployee.user_id` en
L4a—, de modo que los 58 lectores no cambian en este pase. La migración
rellena `model_id` desde `model_name`. `_order` pasa a la forma de la fuente
(`['-model_id', 'id']`). `global` se porta como columna almacenada calculada
de los grupos (`True` sin grupos); el valor escrito por los datos coincide
con el calculado.

**Hallazgo al medir L4d (2026-11-10): `ir.model` no tiene fila para todo
modelo instalado.** De las cuatro reglas de la base de pruebas, dos
(`sale_subscription.CompanyModuleSubscription`,
`sale_subscription.SubscriptionInvoice`) nombran modelos sin fila en
`ir.model`; el módulo `sale_subscription` está `installed` y no tiene
ninguna. Causa: `load_modules` pasa a `init_models` los nombres de
`registry.models`, que sólo conoce los modelos con `_name`, mientras que la
fuente refleja todo modelo del módulo (`_reflect_models` sobre el registro
completo). Consecuencia para L4d: `model_id` no puede ser `NOT NULL` hasta
que la reflexión cubra todo modelo instalado; se declara `null=True` con esta
condición de cierre, y el relleno deja sin `model_id` las filas cuyo modelo
no tiene fila.

L4d implementado: `model_id` (forma C, `CASCADE`, `related_name='rule_ids'`
≙ `ir.model.rule_ids`) con `_sync_model_reference` en `save()`, `global`
añadido con `add_to_class` como la fuente lo añade con `setattr`, almacenado
y calculado de `groups` por el mecanismo de `modified` del `m2m_changed`; la
migración `base.0105` rellena las dos columnas. Un `QuerySet` de Django no
vuelca los calculados pendientes antes de filtrar (la búsqueda de la fuente
sí, `flush_model` de los campos del dominio): la prueba vuelca a mano.

### L4e — el usuario del contexto de evaluación al instalar (medido, pendiente)

Con L4d, la carga de `hr_security.xml` llega a `hr_employee_comp_rule` y su
validación (`_check_domain`, ≙ `@api.constrains('domain_force')`) falla:
`'NoneType' object has no attribute 'id'` al evaluar
`user.employee_id.parent_id.id`. Dos causas medidas:

1. `IrRule._eval_context` usa `user=None` si nadie lo pasa, y dentro de
   `Environment(using, SUPERUSER_ID, {})` `get_current_user()` devuelve
   `None`: no existe el `base.user_root` de la fuente (uid 1), que es el
   `env.user` con el que la fuente instala.
2. `res.users.employee_id` (hr) devuelve `None` sin empleado; en la fuente es
   un recordset vacío, sobre el que `.parent_id.id` es `False`.

Condición de cierre: `env.user` del superusuario existe como registro (la
fila de `base.user_root` o su equivalente declarado) y la lectura de un
Many2one vacío por la ruta del dominio no levanta. Hasta entonces la clave
`data` de los manifiestos de `hr` y `hr_skills` sigue sin activar.

#### L4e — medición de la referencia y del árbol (2026-11-10)

- Fuente: `odoo19c: odoo/addons/base/data/res_users_data.xml:5-11` crea
  `base.user_root` (uid 1) con `partner_id ref="base.partner_root"` y
  `company_id ref="main_company"`; `res_partner_data.xml:15-20` crea
  `base.partner_root` («System», inactivo). La fuente instala con
  `env.user` = ese registro.
- Aquí: `SUPERUSER_ID = 1` (`orm/utils.py:42`), `res_users` vacío en la base
  de pruebas, `get_current_user()` devuelve `None` sin fila con ese id
  (`orm/environments.py:174-187`), y no hay `base.main_company`,
  `base.partner_root` ni `base.user_root` (0 filas de `ir_model_data`). La
  empresa no se siembra a propósito (DEC-3 de `tenants-sin-clases-en-codigo`).
- `ResUsers.partner` es obligatorio y `ResUsers.company` admite nulo
  (`res_users.py:698-733`): un `user_root` sin empresa es posible.

Forma derivada: TRAE `base.partner_root` y `base.user_root` por los datos de
`base` con su XML-ID, sin `company_id` (divergencia declarada: no hay
`main_company`), inactivos, y con el id `SUPERUSER_ID`.

**Riesgo que la medición no cierra:** en una base ya poblada la fila con id 1
puede ser un usuario humano. Este árbol ya trata ese id como superusuario
(`SUPERUSER_ID = 1`), así que el riesgo existe hoy, pero sembrar
`base.user_root` sobre él lo volvería explícito. Desde esta VM no se puede
medir qué hay en las bases desplegadas. Condición de cierre: la ocupación del
id 1 en las bases desplegadas, medida, o una decisión registrada sobre el id
del superusuario.

Segunda mitad, independiente de la primera: `res.users.employee_id` (hr)
devuelve `None`; la fuente devuelve un recordset vacío. La ruta del dominio
`user.employee_id.parent_id.id` necesita que la lectura sobre lo vacío dé
`False`.

#### L4e — replanteo por directiva del ejecutor (2026-11-10)

Directiva: una divergencia que existía porque faltaba la raíz ORM no se
conserva; se implementa como la referencia, clasificando cada pieza en TRAE
(el stack instala el símbolo) o CONSTRUYE (las primitivas están). Población
de la referencia: las cuatro raíces de `odoo18c`, `odoo18e`, `odoo19c` y
`odoo19e`; medido, la segunda raíz de `odoo19c` es
`19.x/odoo-19.0/odoo-19.0/odoo-19.0/odoo/addons` (24 manifiestos), no la
ruta sin el tercer `odoo-19.0`, que no existe.

Consecuencia para la segunda mitad de L4e: `user.employee_id` es un
recordset vacío en la fuente porque `hr.employee` es un modelo del ORM. Aquí
la semántica de recordset existe sólo para las clases que derivan de
`BaseModel` (`orm/models.py`, `_create_result`), y el resto recibe un
`QuerySet`; su adopción es TASK-API-0397. La forma fiel no es una guarda en
el contexto de evaluación sino adoptar `BaseModel` en `hr.employee`
(CONSTRUYE sobre la raíz existente), medir sus consumidores y llevar
`res.users.employee_id` a devolver el recordset. Primera mitad (el registro
del superusuario) sin cambio: sigue abierta la ocupación del id 1.

#### L4e — secuencia derivada (2026-11-10)

Medido tras el replanteo, la regla `hr_employee_comp_rule` necesita cinco
cosas, en este orden:

| # | Qué | TRAE / CONSTRUYE | Evidencia |
|---|---|---|---|
| e1 | `hr.employee` deriva de `BaseModel` | TRAE: la base de recordsets existe; precedente `6dd45001` (grupo A de TASK-API-0397) | con el cambio, 254 de 257 pruebas de `hr`, `hr_skills`, `hr_recruitment`, `fleet`, `sale_timesheet` e `integration/hr` siguen verdes; las 3 rojas son las de los datos de seguridad, sin activar |
| e2 | `hr.employee.parent_id` en forma C (`child_ids` como reverso, `hr_employee.py` de la fuente) | CONSTRUYE sobre ADR-029 | `parent` es forma A: su `parent_id` es el id escalar y `user.employee_id.parent_id.id` falla aunque el empleado exista |
| e3 | `res.users.employee_id`: `Many2one` no almacenado, `compute='_compute_company_employee'`, `search='_search_company_employee'` (`hr/models/res_users.py:64-65`, `:266-286` de la fuente) | TRAE: campos no almacenados calculados del ORM | hoy es la propiedad `employee`, que devuelve `None` |
| e4 | `IrRule._eval_context` toma el usuario del entorno si nadie lo pasa (`user = self.env.user` en `ir_rule.py:38-51` de la fuente) | TRAE: `get_current_user()` | hoy `user=None` |
| e5 | `base.partner_root` y `base.user_root` (uid `SUPERUSER_ID`), como los crea la inicialización de la base de la fuente (`base_data.sql`, no el cargador) | CONSTRUYE en una migración de `base` por los modelos, mismo patrón que `0027_seed_base_groups`; si la fila 1 existe, recibe el XML-ID sin más cambios porque este árbol ya la trata como superusuario | sin fila con id 1, `get_current_user()` es `None` bajo `SUPERUSER_ID` |

Lectura de un `Many2one` sobre un recordset VACÍO: el `FieldDescriptor`
cubre la rama de tamaño de `Field.__get__` (`fields.py:1653-1661` de la
fuente), pero el accesor del attname de una FK en forma A no; con forma C la
ruta del dominio pasa por el campo y no por el attname.

#### L4e — implementación y medición (2026-11-10T20:48:46)

e1–e5 implementados como la tabla anterior. Con ellos la carga real de
`hr_security.xml` avanzó hasta su línea 88 y destapó dos piezas más, y una
tercera que no se cierra en este pase.

| # | Qué destapó | Desenlace | Control de anulación |
|---|---|---|---|
| e6 | `order_to_django` no recorría un `related` sin columna: el `_order = 'name, login'` de `res.users` ordena por el `name` del partner (`_inherits`). ≙ `_order_field_to_sql` → `_field_to_sql` (`odoo19c: odoo/orm/models.py:2919-2922`) | CONSTRUYE: se recorre el camino del `related` y se ordena en el comodelo | retirada la rama, caen exactamente los 3 casos de `tests/unit/orm/test_order_follows_related.py`; los 11 de `test_order_to_sql.py` siguen |
| e7 | el converter de `ir.fields` comparaba el modelo del XML-ID contra `_name` (`ir.model`), pero `ir_model_data.model` guarda la etiqueta de Django (`base.IrModel`), que es la llave declarada en `ir_model.py` («Qué va en `model`»): todo `model_id:id` del CSV de la referencia se rechazaba y la fila llegaba sin `model_id` | se compara con `model._meta.label`; medido, 0 filas del almacén usan la forma `_name`, así que las dos pruebas que la fijaban se alinearon con la etiqueta | restaurada la comparación con `_name`, falla la instalación misma —la carga del CSV de HR va en `post_migrate`— y caen en setup los 21 casos de `test_ir_fields_relational.py` y `test_hr_security_data.py`: discrimina, pero sin aislar los dos casos que dependen de ella |
| e8 | tres reglas —`ir_rule_hr_contract_type_multi_company`, `ir_rule_hr_departure_reason_multi_company`, `ir_rule_hr_payroll_structure_type_multi_company`— evalúan `user.env.companies…` | **bloqueo medido**: exige `res.users` y `res.company` sobre `BaseModel`. Adoptarlo en `res.users` (medido) hizo caer 35 casos del subconjunto `base`/`hr`/`authz`/`orm`: 19 por e6, ya cerrado, y 16 porque el contrato de acceso de `res.users` se activa en los flujos de autenticación (`check_access('read')` sin usuario ni `sudo` en el alta de 2FA, `main_user_id` vacío como recordset). Se revirtió; las tres reglas se omiten en `hr_security.xml` con la omisión declarada en su cabecera | — |

e4 y e5 tienen prueba directa: `test_the_rule_context_takes_the_acting_user`
(retirado e4, cae sólo ese caso entre 19) y `tests/unit/base/test_root_user_seed.py`.
e5 es una migración; su anulación exige una base nueva, y la cubre
ci-multidb (`--create-db`). Las dos pruebas de `test_res_users_constraints.py`
que fabricaban la fila `SUPERUSER_ID` ahora usan la sembrada: con ella
presente, fabricarla viola la clave.

**Sucesor de e8** (sin id acuñado; lo acuña quien tenga el TaskStore):
adoptar `BaseModel` en `res.users` y `res.company`, con el contrato de
acceso de `res.users` en autenticación resuelto como la fuente —el alta de
2FA escribe con `sudo()` (`auth_totp/models/res_users.py:109-110`)— y
`env.user`/`env.companies` devolviendo recordsets. Condición de cierre: las
tres reglas de e8 cargan sin omisión y sus dominios filtran.

### e8 — `res.users` y `res.company` sobre `BaseModel` (diseño, 2026-11-10T21:24:42)

Sucesor declarado de L4e. Medición previa, sobre `feature/vm-x2hokp-orm-root@8ab54be4`:

- `ResCompany` deriva sólo de `TimeStampedModel`; `ResUsers`, de
  `DefaultGetMixin` y `TimeStampedModel`. Ninguno es recordset.
- `env.company`/`env.companies` aparecen 119 veces en `src` y `addons`
  (`grep -rn "env.companies\|env.company\b\|env().company\b"`, sin
  comentarios). Hoy `Environment.companies` devuelve una **lista**
  (`orm/environments.py:1126-1132`); la fuente devuelve un recordset
  (`odoo19c: odoo/orm/environments.py:246-253`).
- **La pieza que explica los 16 casos de autenticación**: en la fuente
  `env.user` es `self(su=True)['res.users'].browse(self.uid)`
  (`environments.py:208-213`). Es un recordset **elevado**, así que leer
  sus campos no pasa por la ACL. Aquí `as_current_user` ya eleva la fila
  (`environments.py:2144`), pero un usuario obtenido por `objects.get` en
  un servicio no: con `BaseModel` ese registro lleva el entorno del
  llamador y `check_access('read')` lo rechaza. Los ocho casos de TOTP
  (`test_totp.py`, `test_totp_recovery.py`, `test_rpc_api_key_channel.py`)
  caen así. La fuente escribe el secreto con `self.sudo()`
  (`auth_totp/models/res_users.py:109-110`).

Población que cae al adoptarlo en `res.users` (medida antes de revertir):
`test_totp.py`, `test_totp_recovery.py`, `test_rpc_api_key_channel.py`,
`test_res_partner_user_and_lang.py` (`main_user_id` vacío pasa a ser
`res.users()`, como en la fuente), `test_res_users_constraints.py` (ya
resuelto por la siembra de 0106), `test_contract_access_on_read_reference.py`,
`test_read_group_postprocess.py` (sus dos casos usan `res.users` como
ejemplo de comodelo de Django; hay que elegir otro) y
`test_field_lifecycle_methods.py` (ya resuelto).

Secuencia derivada:

| # | Qué | TRAE / CONSTRUYE |
|---|---|---|
| e8a | `Environment.user` devuelve el recordset elevado de `res.users`, y los servicios que reciben una fila la elevan como la fuente (`sudo()` en el alta de 2FA) | TRAE: `as_current_user` y `sudo` existen |
| e8b | `ResUsers` sobre `BaseModel`; las pruebas que usan `res.users` como «comodelo de Django» pasan a otro modelo que siga fuera de `BaseModel` | TRAE: precedente `hr.employee` (e1) |
| e8c | `ResCompany` sobre `BaseModel`; `env.company`/`env.companies` devuelven recordsets; se miden los 119 consumidores | TRAE |
| e8d | se restauran en `hr_security.xml` las tres reglas omitidas | — |

Condición de cierre: las tres reglas de e8d cargan y filtran por el país de
las empresas activas, y el gate completo y ci-multidb siguen verdes.
