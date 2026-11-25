# Adopción de BaseModel: ir.module.module.dependency + .exclusion (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_module.py:999` — `class IrModuleModuleDependency(models.Model)`, `_name = 'ir.module.module.dependency'`.
- `odoo19c: odoo/addons/base/models/ir_module.py:1065` — `class IrModuleModuleExclusion(models.Model)`, `_name = 'ir.module.module.exclusion'`.
- ACL (`ir.model.access.csv`): `group_system` para los dos, ya sembrada en
  `src/addons/base/security/ir_model_access.py`.

## Cambio

- `src/addons/base/models/ir_module.py`: `IrModuleDependency(models.BaseModel,
  TimeStampedModel)` e `IrModuleExclusion(models.BaseModel, TimeStampedModel)`.
  Sin migración (`./kaupamex-bin makemigrations base --check --dry-run` → sin
  cambios). `IrModule` sigue fuera: es otra unidad.
- El gate de estilo mide la clase entera cuando cambia su cabecera; se pagan
  las 19 incidencias heredadas de las dos clases (alineación en `Meta`, líneas
  largas). Sin cambio de conducta.
- `IrModuleDependency._compute_depend_batch` sólo se reflowa: el conjunto de
  alias y el índice por nombre se parten en líneas ≤ 79, con el mismo cuerpo.
  Referencia: `_compute_depend` (`odoo19c: odoo/addons/base/models/ir_module.py:1022`),
  que busca los módulos por nombre y asigna `depend_id`. Prueba:
  `tests/integration/base/test_ir_module_dependencies.py`.

## Pruebas

- `tests/unit/base/test_ir_module_reference_shape.py`:
  `test_dependency_and_exclusion_are_basemodel` (nuevo, por modelo).
- Subconjunto derivado: los consumidores de `IrModuleDependency`,
  `IrModuleExclusion`, `update_module_list` (120 passed) y el más ancho de
  `IrModule` / `ir.module.module` (29 archivos, 369 passed).

## Anulación

Revertir sólo `IrModuleExclusion` a `TimeStampedModel`: cae exactamente
`test_dependency_and_exclusion_are_basemodel[IrModuleExclusion]` (1 de 7).
Restaurado y verificado con `cmp`.
