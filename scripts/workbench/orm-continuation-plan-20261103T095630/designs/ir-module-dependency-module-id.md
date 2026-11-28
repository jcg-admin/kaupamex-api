# `module_id` en dependencias y exclusiones; `dependencies_id` y `exclusion_ids`

Sucesora de `designs/ir-module-group-b.md`. TASK-API-0397.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_module.py`:

- `:295-296` `dependencies_id = fields.One2many('ir.module.module.dependency', 'module_id', string='Dependencies', readonly=True)`.
- `:298-299` `exclusion_ids = fields.One2many('ir.module.module.exclusion', 'module_id', string='Exclusions', readonly=True)`.
- `ir.module.module.dependency` y `ir.module.module.exclusion` declaran
  `module_id = fields.Many2one('ir.module.module', 'Module', ondelete='cascade')`
  (`:1009`, `:1074`); sus SQL de `_update_dependencies` y `_update_exclusions`
  (`:829-860`) escriben la columna `module_id`.

## Lo que el puerto tenía y diverge

Las dos FK se llaman `module` (columna `module_id`, la de Django por omisión)
con `related_name='dependencies'` / `'exclusions'`.
`scripts/fk_naming_baseline.txt` ya las lista como deuda de nombre
(`IrModuleDependency.module`, `IrModuleExclusion.module`).

Forma C: el campo pasa a `module_id` con `db_column='module_id'` y
`related_name='+'`; la migración es sólo de estado (`SeparateDatabaseAndState`
con `RenameField` + `AlterField`), porque la columna ya se llama `module_id`.
`IrModule` gana los dos One2many de la fuente. Las dos líneas salen del
baseline.

Consumidores medidos (`grep` de `module=`, `module__`, `.dependencies`,
`.exclusions` y `IrModuleDependency`/`IrModuleExclusion`): el propio
`ir_module.py` (`_request_module_change`, `all_dependencies`), los
`objects.create(module=...)` de las pruebas y los filtros `module__name` de
`test_module_catalog_database.py` y `test_module_state_requests.py`.

También se corrige la prosa heredada del docstring de `IrModule`: decía
«9 de 31» campos; medido por AST, el puerto declara 20 de los 31 de la fuente.

## Pruebas (RED)

`tests/unit/base/test_ir_module_dependency_module_id.py`: el nombre y la
columna de las dos FK, y los dos One2many leídos desde un módulo.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrModuleDependency.module_id` (forma C, `db_column='module_id'`, `related_name='+'`) | `src/addons/base/models/ir_module.py` | `odoo19c: odoo/addons/base/models/ir_module.py:1009` |
| `IrModuleExclusion.module_id` (forma C) | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:1074` |
| `IrModule.dependencies_id` y `IrModule.exclusion_ids` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:295-299` |
| `IrModule._request_module_change` y `IrModuleDependency.all_dependencies`: filtran por `module_id__name` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:1009` |
| docstring de `IrModule`: cobertura medida 22 de 31 | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:158-330` |
| migración `0155_ir_module_dependency_module_id`: sólo de estado | `src/addons/base/migrations/0155_ir_module_dependency_module_id.py` | `odoo19c: odoo/addons/base/models/ir_module.py:1009,1074` |
| `update_module_list`: el id crudo va por el `attname` `module_id_id` | `src/addons/base/management/commands/update_module_list.py` | `odoo19c: odoo/addons/base/models/ir_module.py:829-840` |

`scripts/fk_naming_baseline.txt` pierde `IrModuleDependency.module` e
`IrModuleExclusion.module`: es la deuda de nombre que esta unidad salda.

Medido al implementar: `get_field('module_id')` de Django resuelve también el
`attname` de un campo `module`, así que la primera versión de la prueba del
nombre pasaba antes del cambio; ahora afirma `field.name`. Y
`update_module_list` creaba filas con `module_id=module.pk`, que era el
`attname`; con el campo renombrado el id crudo va por `module_id_id`.

Pruebas: `tests/unit/base/test_ir_module_dependency_module_id.py` (3 casos;
RED 3 de 3). Consumidores corregidos: `test_ir_module_dependencies.py`,
`test_ir_module_group_b.py`, `test_install_request_wizard.py`,
`test_module_catalog_database.py`, `test_module_state_requests.py`
(94 pruebas en verde).

Anulación (copia restaurada y comparada con `cmp`): sin `dependencies_id` cae
exactamente el caso de los One2many (1 de 11).
