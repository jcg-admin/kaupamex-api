# TASK-API-0516 — Calcular los calculados almacenados que añade una migración

Fecha: 2026-11-10. Referencia: odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato

`BaseModel._auto_init` (`odoo19c: odoo/orm/models.py:3220-3238`): por cada
campo almacenado, `field.update_db` devuelve si la columna es nueva; si lo
es y el campo es calculado, todas las filas existentes se marcan para
cómputo (`env.add_to_compute(field, records)`), *"so that computed required
fields are flushed before the NOT NULL constraint is added"*. El
`parent_path` nuevo se calcula con `_parent_store_compute` (`:3201-3204`,
`:3246-3247`).

## Estado medido

- `parent_path`: **satisfecho en la misma autoridad**. La migración que lo
  introduce lo calcula con `RunPython`
  (`src/addons/base/migrations/0100_ir_ui_menu_parent_path.py`, ≙
  `_parent_store_compute`).
- Calculados almacenados: **30** campos calculados almacenados entraron por
  `AddField` sobre tablas existentes (fuera de migraciones iniciales) y
  ninguno se calcula sobre las filas previas
  (`scratchpad/probe-addfield-computed.py`): `account` 1, `base` 2, `crm` 16,
  `sale` 6, `test_orm` 4. En una base con datos, esas columnas quedan en
  `NULL` o en el default hasta que algo vuelva a escribir la fila.

## Decisión

La autoridad del esquema son las migraciones (TASK-API-0515), así que el
cálculo es una **operación de migración**, no `_auto_init`:

- `orm.migration_operations.ComputeStoredFields(app_label, model_name,
  field_names)`: una operación sobre `RunPython` que toma la clase real del
  modelo (el cómputo necesita sus métodos; el modelo histórico no los tiene,
  igual que la fuente usa el código vigente), marca todas las filas con
  `add_to_compute` y vuelca con `flush_model(field_names)`. Reversa: no-op
  (los valores calculados no se deshacen).
- Toda migración que añada un calculado almacenado a una tabla existente lo
  sigue con esta operación.
- Para los 30 ya aplicados, una migración nueva por app (5) con la misma
  operación: las migraciones viejas ya corrieron en las bases desplegadas y
  editarlas no recalcula nada.

## Casos (RED)

1. Fila existente con la columna en `NULL`; la operación la deja con el
   valor de su cómputo.
2. La operación sobre una tabla vacía no falla ni consulta de más.
3. Varios campos de un mismo cómputo (`size1`, `size2`) se calculan en una
   sola pasada.
4. Guardián: una prueba recorre las migraciones y exige que cada `AddField`
   de un calculado almacenado sobre tabla existente vaya seguido de
   `ComputeStoredFields` para ese campo (o figure en la migración de
   rescate de su app).

Anulación prevista: con la operación vaciada caen 1 y 3; el guardián cae al
retirar una migración de rescate.
