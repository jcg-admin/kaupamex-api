# Adopción de BaseModel: ir.model.inherit (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/ir_model.py:1422` — `class IrModelInherit(models.Model)`, `_name = 'ir.model.inherit'`, `_log_access = False`.
- ACL (`ir.model.access.csv:13`): `access_ir_model_inherit`, sin grupo y con
  los cuatro permisos a cero; ya sembrada. Lo escribe el registro con
  privilegio (`_reflect_inherits`).

## Cambio

- `src/addons/base/models/ir_model.py`: `IrModelInherit(models.BaseModel)` en
  lugar de `models.RecordLoaderMixin, models.Model` (BaseModel ya lleva el
  mixin). Sin migración (`./kaupamex-bin makemigrations base --check --dry-run`
  → sin cambios); `_log_access = False` se conserva.
- `tests/integration/test_orm/test_index_method.py::test_a_django_model_without_basemodel_is_walked_by_its_fields`
  usaba `ir.model.inherit` como sujeto «modelo de Django sin BaseModel». El
  sujeto pasa a `ir.module.category`, que sigue sin BaseModel y lleva un campo
  indexado (`parent`).

## Pruebas

- `tests/unit/base/test_ir_model_inherit_basemodel.py` (nuevo).
- Subconjunto derivado (`IrModelInherit|_reflect_inherits|IrModel|ir.model|reflect`,
  128 archivos, `-n 4`): 1615 passed, 5 skipped, 1 failed — el sujeto de
  `test_index_method` arriba, ya corregido (el archivo da 3 passed).

## Anulación

Revertir la base a `RecordLoaderMixin, models.Model`: cae exactamente
`test_model_inherit_is_basemodel` (1 de 4 entre ese archivo y
`test_index_method.py`). Restaurado y verificado con `cmp`.
