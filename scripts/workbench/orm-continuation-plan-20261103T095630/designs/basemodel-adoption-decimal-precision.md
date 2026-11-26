# Adopción de BaseModel: decimal.precision (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/decimal_precision.py:9` — `class DecimalPrecision(models.Model)`, `_name = 'decimal.precision'`.
- `precision_get` (`:23-27`) lee con SQL crudo, sin pasar por la ACL.
- ACL (`ir.model.access.csv:2`): `access_decimal_precision_config`,
  `group_system` 1,1,0,0; ya sembrada.

## Cambio

- `src/addons/base/models/decimal_precision.py`: `DecimalPrecision(models.OriginMixin,
  models.BaseModel)` en lugar de `RecordLoaderMixin, OriginMixin, Model`
  (BaseModel ya lleva el mixin de carga). Sin migración
  (`./kaupamex-bin makemigrations base --check --dry-run` → sin cambios).
- `precision_get` lee por `objects.filter(...).values_list(...)`: el gestor no
  filtra por la ACL (sonda de `designs/basemodel-adoption-ir-module-category-privilege.md`),
  así que sigue leyéndose para cualquier usuario, como el SQL de la fuente.

## Pruebas

- `tests/unit/base/test_decimal_precision_basemodel.py` (nuevo).
- Subconjunto derivado (`DecimalPrecision|decimal.precision|precision_get|get_precision|dp.get`,
  9 archivos, `-n 4`): 73 passed, 3 skipped.

## Anulación

Revertir la base: cae exactamente `test_decimal_precision_is_basemodel` (1 de 1).
Restaurado y verificado con `cmp`.
