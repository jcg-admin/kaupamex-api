# Adopción de BaseModel: ir.module.module (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_module.py:157` — `class
  IrModuleModule(models.Model)`, `_name = 'ir.module.module'`.
- Sus dependencias y exclusiones ya son `BaseModel`
  (`designs/basemodel-adoption-ir-module-dependency-exclusion.md`); aquella
  unidad dejó fuera a `IrModule` como «otra unidad».

## Inventario medido de la clase

La fuente declara 42 métodos en `IrModuleModule`; el puerto, 13. Faltan 33:
`_get_desc`, `_get_views`, `_get_icon_image`, `_compute_has_iap`,
`_unlink_except_installed`, `unlink`, `_get_modules_to_load_domain`,
`check_external_dependencies`, `_state_update`, `button_immediate_install`,
`button_reset_state`, `check_module_update`, `module_uninstall`,
`_remove_copied_views`, `next`, `_button_immediate_function`,
`button_immediate_uninstall`, `button_uninstall_wizard`,
`button_immediate_upgrade`, `get_values_from_terp`, `create`, `update_list`,
`_update_from_terp`, `_update_dependencies`, `_update_countries`,
`_update_exclusions`, `_update_category`, `_update_translations`, `_check`,
`_installed`, `search_panel_select_range`, `_load_module_terms`,
`_extract_resource_attachment_translations`. La adopción es la condición de
todos ellos —usan `self.env`—, y cada grupo es una unidad sucesora.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrModule(models.BaseModel, TimeStampedModel)` | `src/addons/base/models/ir_module.py` | `odoo19c: odoo/addons/base/models/ir_module.py:157` |
| `IrModule._request_module_change`, `IrModule._get_id`: sólo reflow (el gate mide la clase entera al cambiar su cabecera) | ídem | — (sin cambio de cuerpo) |

Sin migración: `makemigrations --check --dry-run` sin cambios. Las 56
incidencias de estilo heredadas de la clase (alineaciones E221/E241, E128 y
líneas largas) se pagan sin cambio de conducta.

Prueba: `tests/unit/base/test_ir_module_reference_shape.py::
test_module_is_basemodel`.

Anulación (copia restaurada y comparada con `cmp`): con la cabecera de vuelta
a `TimeStampedModel` cae exactamente ese caso (1 de 8).

Subconjunto derivado (30 archivos que nombran `IrModule` o
`ir.module.module`): `334 passed`.
