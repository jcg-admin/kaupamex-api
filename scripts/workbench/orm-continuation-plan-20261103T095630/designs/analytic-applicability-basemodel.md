# analytic-applicability-basemodel-0397 — etapa C: `account.analytic.applicability` sobre `BaseModel`

Fecha: 2026-11-22T07:20:30. Etapa C de `designs/analytic-plan-basemodel.md`.

## Referencia

- `odoo19c: addons/analytic/models/analytic_plan.py:405-455` — cabecera
  (`_name`, `_description`, `_check_company_auto`,
  `_check_company_domain = check_company_domain_parent_of`), campos
  `analytic_plan_id`, `business_domain`, `applicability`, `company_id`
  (por defecto `self.env.company`), `create`/`write`/`_unlink_clear_cache`
  y `_get_score`.
- `odoo19c: addons/account/models/account_analytic_plan.py:6-82` — la
  extensión de `account`: `business_domain` (selection_add), `account_prefix`,
  `product_categ_id`, `display_account_prefix` y
  `account_prefix_placeholder` calculados, `_get_score`.
- `hr_timesheet` y `sale` sólo amplían `business_domain`.

## Estado heredado (consumidor en `d6f86336`)

| Contrato | Consumidor | Clase |
|---|---|---|
| cabecera y `BaseModel` | `models.Model` | ABSENT |
| `analytic_plan_id`, `company_id`, `product_categ_id` | `analytic_plan`, `company`, `product_categ` (nombres de Django) | DIVERGENT |
| `company_id` por defecto `env.company` | sin default | ABSENT |
| `_check_company_auto` | ausente | ABSENT |
| `display_account_prefix`, `account_prefix_placeholder` como cómputos sobre recordset | cómputos por instancia de `_add_if_absent` | DIVERGENT |
| `_get_score` (base y `account`) | portados | SATISFIED |
| `create`/`write`/`_unlink_clear_cache` | ausentes | DEPENDENCY (`get_relevant_plans` y su caché de cursor, etapa D-2) |

## Cambio previsto

1. `AccountAnalyticApplicability(models.BaseModel, models.RecordLoaderMixin)`
   con la cabecera de la fuente; `analytic_plan` → `analytic_plan_id`,
   `company` → `company_id` (por defecto la empresa activa), con
   `AlterField` + `RenameField` y las cuatro columnas de log-access.
2. En `account`: `product_categ` → `product_categ_id`; los dos cómputos como
   métodos `@api.depends` sobre el recordset.
3. Consumidores: `AccountAnalyticPlan._get_applicability` lee
   `applicability_ids` como recordset; las pruebas que crean reglas por el
   gestor de Django pasan al ORM.

## Símbolos, referencia y prueba

Prueba: `tests/unit/analytic/test_analytic_applicability_basemodel.py`.

| Símbolo | Referencia |
|---|---|
| `AccountAnalyticApplicability` (cabecera y campos) | `odoo19c: addons/analytic/models/analytic_plan.py:405-431` |
| `0018_applicability_basemodel` | `odoo19c: addons/analytic/models/analytic_plan.py:411-431` |
| `AccountAnalyticPlan._get_applicability` | `odoo19c: addons/analytic/models/analytic_plan.py:246-265` |
| `apply_account_extensions` (`product_categ_id`, cómputos) | `odoo19c: addons/account/models/account_analytic_plan.py:20-82` |

## Lo que esta unidad no cierra

- `create`, `write` y `_unlink_clear_cache` limpian la caché de
  `get_relevant_plans`, que es de la etapa D-2: se portan con ella.
