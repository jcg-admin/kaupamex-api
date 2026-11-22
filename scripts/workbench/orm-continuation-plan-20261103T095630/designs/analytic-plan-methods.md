# analytic-plan-methods-0397 — etapa D-1 de `account.analytic.plan`

Fecha: 2026-11-22T05:37:10. Etapa D de `designs/analytic-plan-basemodel.md`
(«los métodos NOT_VERIFIED, uno a uno contra `:105-403`»), partida en dos: D-1
son los que no dependen de las columnas dinámicas del plan (etapa B); D-2,
los que sí.

## Referencia

- `odoo19c: addons/analytic/data/analytic_data.xml:13-17` — siembra el plan
  `analytic_plan_projects` («Project», `default_applicability=optional`) y
  `analytic.project_plan = 1`.
- `odoo19c: addons/analytic/models/analytic_plan.py:104-113` —
  `__get_all_plans` (con `@ormcache()`) y `_get_all_plans`.
- `odoo19c: addons/analytic/models/analytic_plan.py:115-121` —
  `_strict_column_name`, `_column_name`.
- `odoo19c: addons/analytic/models/analytic_plan.py:185-212` —
  `_onchange_parent_id`, `action_view_analytical_accounts`,
  `action_view_children_plans`.
- `odoo19c: addons/analytic/models/analytic_plan.py:246-265` —
  `_get_applicability`.
- `odoo19c: addons/analytic/models/analytic_plan.py:277-282` —
  `_hierarchy_name`.

## Estado heredado (consumidor en `2bbdd213`)

| Contrato | Consumidor | Clase |
|---|---|---|
| plan «Project» y `analytic.project_plan` sembrados | ausentes (0 menciones de `analytic.project_plan`) | ABSENT |
| `__get_all_plans` / `_get_all_plans` | ausentes | ABSENT |
| `_strict_column_name`, `_column_name` | ausentes | ABSENT |
| `_onchange_parent_id`, `action_view_*` | ausentes | ABSENT |
| `_get_applicability` | ausente; `_get_score` sí está (`analytic_plan.py:364`) | ABSENT |
| `_hierarchy_name` | ausente | ABSENT |
| `get_relevant_plans`, `unlink`, `create`, `write`, `_find_*`, `_sync_*`, `_is_subplan_field_used`, `_auto_init`, `_inverse_*` | ausentes | DEPENDENCY (etapa B, columnas dinámicas) → D-2 |

## Cambio previsto

1. Migración de datos `analytic/0017`: crea el plan «Project» con su `xml_id`
   y fija `analytic.project_plan` a su id si el parámetro no existe.
2. Los métodos de D-1 en `AccountAnalyticPlan`, con los nombres de la fuente
   (`__get_all_plans` queda como `_AccountAnalyticPlan__get_all_plans` por la
   misma regla de Python que allá).
3. `__get_all_plans` lleva `@ormcache()` como la fuente. Allá la caché se
   limpia porque crear o borrar un plan raíz crea o borra su columna dinámica
   y eso recarga el registro; sin la etapa B ese camino no existe, así que
   `create` y `unlink` limpian la caché del registro explícitamente
   (`clear_cache()`), que es el efecto que la columna produciría. Se retira
   cuando la etapa B traiga las columnas.

## Símbolos, referencia y prueba

Prueba: `tests/unit/analytic/test_analytic_plan_methods.py`.

| Símbolo | Referencia |
|---|---|
| `0017_seed_project_plan` | `odoo19c: addons/analytic/data/analytic_data.xml:13-17` |
| `AccountAnalyticPlan._AccountAnalyticPlan__get_all_plans`, `_get_all_plans` | `odoo19c: addons/analytic/models/analytic_plan.py:104-113` |
| `AccountAnalyticPlan._strict_column_name`, `_column_name` | `odoo19c: addons/analytic/models/analytic_plan.py:115-121` |
| `AccountAnalyticPlan._onchange_parent_id` | `odoo19c: addons/analytic/models/analytic_plan.py:185-188` |
| `AccountAnalyticPlan.action_view_analytical_accounts`, `action_view_children_plans` | `odoo19c: addons/analytic/models/analytic_plan.py:190-212` |
| `AccountAnalyticPlan._get_applicability` | `odoo19c: addons/analytic/models/analytic_plan.py:246-265` |
| `AccountAnalyticPlan._hierarchy_name` | `odoo19c: addons/analytic/models/analytic_plan.py:277-282` |

## Casos de prueba

- sin parámetro `analytic.project_plan` válido, `_get_all_plans` levanta
  `UserError`; con él, devuelve el plan de proyecto y los demás raíz;
- `_strict_column_name` da `account_id` para el de proyecto y `x_plan<id>_id`
  para otro; `_column_name` de un subplan es el de su raíz;
- poner padre al plan de proyecto levanta `UserError`;
- las dos acciones devuelven el dict de la fuente;
- `_get_applicability` respeta `applicability` forzado y elige la regla de
  mayor puntaje, o cae al `default_applicability`;
- `_hierarchy_name` da `(profundidad, nombre)` y antepone `x_` a `account_id`;
- crear un plan raíz nuevo aparece en `_get_all_plans` (la caché se limpia).
