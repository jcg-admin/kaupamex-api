# Adopción de BaseModel: ir.exports + ir.exports.line (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_exports.py:7` — `class IrExports(models.Model)`, `_name = 'ir.exports'`.
- `odoo19c: odoo/addons/base/models/ir_exports.py:17` — `class IrExportsLine(models.Model)`, `_name = 'ir.exports.line'`.
- En la fuente todo modelo con `_name` hereda `BaseModel`: ACL, record rules,
  `copy`, `create` y la API de recordset aplican a los dos.

## Cambio

- `src/addons/base/models/ir_exports.py`: `IrExports(BaseModel, TimeStampedModel)`
  e `IrExportsLine(BaseModel)`. Sin migración (`kaupamex-bin makemigrations base
  --check --dry-run` sin cambios): el mixin no añade columnas.
- La ACL ya estaba sembrada (`src/addons/base/security/ir_model_access.py`):
  `access_ir_exports_group_system` (`base.group_allow_export`) y
  `access_ir_exports_line_group_system` (`base.group_user`), como la fuente.

## Consumidores y pruebas

- `tests/unit/base/test_ir_exports.py`: `test_both_models_are_basemodel`
  (nuevo); los casos de copia pasan a `sudo()` (las pruebas de la fuente corren
  como superusuario; sin usuario, la ACL de BaseModel rehúsa) y leen por la API
  de recordset (`mapped`, `.ids`, `len`).
- `tests/unit/orm/test_copy_universality.py` y `test_create_universality.py`:
  el sujeto Django-only deja de ser `IrExports` (ya es BaseModel) y pasa a
  `ExportJob`, que sigue fuera de BaseModel.

## Anulación

Revertir sólo `IrExportsLine` a `RecordLoaderMixin, models.Model`: caen
exactamente 3 de 6 en `test_ir_exports.py` (el caso BaseModel de la línea y los
dos de copia de líneas); los otros 3 sobreviven. Restaurado y verificado con
`cmp`.
