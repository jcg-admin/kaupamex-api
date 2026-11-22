# analytic-relevant-plans-0397 — etapa D-2a: `get_relevant_plans` y su caché

Etapa D-2 de `designs/analytic-plan-methods.md`, primera mitad. Depende de
`cursor-cache-0397` (`env.cr.cache`) y de
`analytic-account-related-fields-0397` (`root_plan_id`).

## Referencia

- `odoo19c: addons/analytic/models/analytic_plan.py:214-244` —
  `get_relevant_plans`: memoriza en `env.cr.cache['get_relevant_plans']`
  por `frozendict(kwargs)` la lista de planes raíz con cuentas y no
  `unavailable`, más los planes de cuentas ya elegidas.
- `odoo19c: addons/analytic/models/analytic_plan.py:272-275` — `unlink`
  vacía esa caché.
- `odoo19c: addons/analytic/models/analytic_plan.py:372-379` — `create` la
  vacía siempre; `write`, si cambia `default_applicability`.
- `odoo19c: addons/analytic/models/analytic_plan.py:433-443` — la regla de
  aplicabilidad la vacía en `create`, `write` y `_unlink_clear_cache`.

## Estado heredado (consumidor en `892034dd` + `f87622cd`)

| Contrato | Consumidor | Clase |
|---|---|---|
| `get_relevant_plans` | ausente | ABSENT |
| vaciado de la caché en `create`/`write`/`unlink` del plan y de la regla | ausente | ABSENT |
| el resto de `write` del plan (`_update_accounts_in_analytic_lines`) y de `unlink` (columnas dinámicas) | ausente | DEPENDENCY (etapa B) |

## Cambio previsto

1. `AccountAnalyticPlan.get_relevant_plans(**kwargs)` sobre
   `self.env.cr.cache`, con la clave `frozendict(kwargs)` de `tools.misc`.
2. `create` y `unlink` del plan vacían la caché además de la del registro
   (etapa D-1); `write` la vacía si cambia `default_applicability`.
3. La regla de aplicabilidad la vacía en `create`, `write` y `unlink` (este
   stack no tiene `@api.ondelete`: `_unlink_clear_cache` es el `unlink`,
   como en `addons/hr/models/hr_departure_reason.py:28-30`).

## Símbolos, referencia y prueba

Prueba: `tests/unit/analytic/test_analytic_relevant_plans.py`.

| Símbolo | Referencia |
|---|---|
| `AccountAnalyticPlan.get_relevant_plans` | `odoo19c: addons/analytic/models/analytic_plan.py:214-244` |
| `AccountAnalyticPlan.create`, `unlink`, `write` (vaciado) | `odoo19c: addons/analytic/models/analytic_plan.py:372-379` |
| `AccountAnalyticApplicability.create`, `write`, `unlink` | `odoo19c: addons/analytic/models/analytic_plan.py:433-443` |

## Casos de prueba

- un plan raíz con cuentas aparece con su `applicability`, `color`,
  `all_account_count` y `column_name`; uno sin cuentas, no;
- un plan `unavailable` no aparece, salvo que una cuenta elegida sea suya, y
  entonces sale `optional`;
- la segunda llamada con los mismos argumentos sale de la caché;
- crear un plan, cambiar `default_applicability` o tocar una regla vacía la
  caché.
