# analytic-plan-basemodel-0397 — `account.analytic.plan` sobre `BaseModel`

## Referencia

`odoo19c: addons/analytic/models/analytic_plan.py:13-92` (cabecera y campos),
`:123-188` (inversos, cómputos, búsqueda y onchange), `:214-403` (planes
relevantes, aplicabilidad, `unlink`, columnas dinámicas, `create`/`write`).

## Inventario por contrato (consumidor en `630ceca4`)

| Contrato de la fuente | Consumidor | Clase |
|---|---|---|
| `_name`, `_description`, `_parent_store`, `_rec_name='complete_name'`, `_order='sequence asc, id'` (`:14-18`) | `models.Model`; `Meta.ordering` | ABSENT |
| `parent_id` (`:29-36`), `children_ids` (`:43-47`) | `parent`, `children` (nombres de Django) | DIVERGENT |
| `parent_path` mantenido por el ORM (`:16`, `:37`) | `save()` a mano | DIVERGENT |
| `complete_name` almacenado y recursivo (`:52-57`, `:139-145`) | `property` iterativa | DIVERGENT |
| `root_id` calculado con búsqueda (`:38-42`, `:129-137`) | `property root` | DIVERGENT |
| `children_count`, `account_count` (`:48-51`, `:63-66`, `:147-151`, `:180-182`) | `property` | DIVERGENT |
| `all_account_count` (`:67-70`, `:152-178`) | ausente | ABSENT |
| `_inverse_name`, `_inverse_parent_id`, `_sync_*`, `_find_plan_column`, `_find_related_field`, `_column_name`, `_strict_column_name` (`:115-127`, `:299-372`) | ausentes: no hay columnas dinámicas | DEPENDENCY (columnas dinámicas de `analytic.plan.fields.mixin`) |
| `_auto_init` (`:94-103`) | ausente | DEPENDENCY (mismo mecanismo) |
| `__get_all_plans`, `_get_all_plans`, `get_relevant_plans`, `_get_applicability`, `_hierarchy_name`, `_is_subplan_field_used`, `unlink`, `create`, `write`, `_onchange_parent_id`, acciones (`:105-113`, `:185-297`, `:374-403`) | parcial o ausente | NOT_VERIFIED |
| `account.analytic.applicability` (`:405-455`) | `models.Model` | ABSENT (etapa C) |

## Etapas

- **A (esta unidad):** `BaseModel` y cabecera; `parent` → `parent_id` y
  `children` → `children_ids` con migración `AlterField`+`RenameField`;
  `_parent_store` del ORM en lugar del `save()` a mano; `complete_name`
  almacenado y recursivo con migración que lo rellena; `root_id`,
  `children_count`, `account_count` y `all_account_count` como campos
  calculados; consumidores de `.root`/`.parent`/`.children` adaptados.
  Precedente medido: `addons/product/models/product_category.py:54-138`.
- **B:** columnas dinámicas del plan (dependen del mixin de campos de plan).
- **C:** `account.analytic.applicability` sobre `BaseModel`.
- **D:** los métodos NOT_VERIFIED, uno a uno contra `:105-403`.

## Pruebas (etapa A)

`tests/unit/analytic/test_analytic_plan_basemodel.py`: el modelo es
`BaseModel` con la cabecera de la fuente; `complete_name` se almacena y se
recalcula al renombrar el padre; `root_id` y su búsqueda; los contadores sobre
un recordset de dos planes; `parent_path` lo mantiene el ORM al mover un plan.

## Símbolos de la etapa A, con su referencia y su prueba

Prueba de todos: `tests/unit/analytic/test_analytic_plan_basemodel.py`.

| Símbolo | Referencia |
|---|---|
| `AccountAnalyticPlan._compute_root_id` | `odoo19c: addons/analytic/models/analytic_plan.py:129-132` |
| `AccountAnalyticPlan._search_root_id` | `odoo19c: addons/analytic/models/analytic_plan.py:134-137` |
| `AccountAnalyticPlan._compute_complete_name` | `odoo19c: addons/analytic/models/analytic_plan.py:139-145` |
| `AccountAnalyticPlan._compute_analytic_account_count` | `odoo19c: addons/analytic/models/analytic_plan.py:147-150` |
| `AccountAnalyticPlan._compute_all_analytic_account_count` | `odoo19c: addons/analytic/models/analytic_plan.py:152-178` |
| `AccountAnalyticPlan._compute_children_count` | `odoo19c: addons/analytic/models/analytic_plan.py:180-182` |
| `0016_plan_parent_id_complete_name` (renombre y relleno) | `odoo19c: addons/analytic/models/analytic_plan.py:29-57` |
