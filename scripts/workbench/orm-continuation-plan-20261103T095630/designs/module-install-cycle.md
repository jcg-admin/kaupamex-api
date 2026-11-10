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
