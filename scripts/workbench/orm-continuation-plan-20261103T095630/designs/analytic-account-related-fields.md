# analytic-account-related-fields-0397 — `root_plan_id` y `color` de la cuenta analítica

Fecha: 2026-11-22T09:15:04. Prerrequisito de la etapa D-2 del plan analítico:
`get_relevant_plans` lee `root_plan_id` de las cuentas
(`odoo19c: addons/analytic/models/analytic_plan.py:214-244`).

## Referencia

- `odoo19c: addons/analytic/models/analytic_account.py:44-49` —
  `root_plan_id = Many2one('account.analytic.plan', related="plan_id.root_id",
  store=True)`.
- `odoo19c: addons/analytic/models/analytic_account.py:50-53` —
  `color = Integer(related='plan_id.color')`.

## Estado heredado (consumidor en `cc91fbbb`)

| Contrato | Consumidor | Clase |
|---|---|---|
| `root_plan_id` relacionado y almacenado | `property root_plan` (`analytic_account.py:161-165`) | DIVERGENT |
| `color` relacionado | `property color` (`analytic_account.py:168-170`) | DIVERGENT |

## Cambio previsto

1. `root_plan_id` como `Many2one` con `related='plan_id.root_id'` y
   `store=True`, columna `root_plan_id`; migración que la añade y la calcula
   sobre las filas existentes con `ComputeStoredFields`.
2. `color` como `Integer` con `related='plan_id.color'`, sin columna.
3. El único consumidor de `.root_plan` (una prueba) pasa a `.root_plan_id`.

## Símbolos, referencia y prueba

Prueba: `tests/unit/analytic/test_analytic_account_related_fields.py`.

| Símbolo | Referencia |
|---|---|
| `AccountAnalyticAccount.root_plan_id` | `odoo19c: addons/analytic/models/analytic_account.py:44-49` |
| `AccountAnalyticAccount.color` | `odoo19c: addons/analytic/models/analytic_account.py:50-53` |
| `0019_account_root_plan_id` | `odoo19c: addons/analytic/models/analytic_account.py:44-49` |

## Casos de prueba

- `root_plan_id` es la raíz del plan y se guarda en su columna;
- mover el plan bajo otro padre recalcula `root_plan_id` de sus cuentas;
- se busca por `root_plan_id`;
- `color` sigue al del plan.
