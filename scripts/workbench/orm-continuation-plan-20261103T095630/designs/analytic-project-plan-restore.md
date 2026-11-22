# analytic-project-plan-restore-0397 — la semilla del plan de proyecto sobrevive al flush

Fecha: 2026-11-22T10:28:26. Corrige `analytic-plan-methods-0397` (`designs/analytic-plan-methods.md`,
asentada en `5d7a9892`).

## Episodio

El F2 de `892034dd` falló en
`tests/unit/analytic/test_analytic_plan_methods.py::test_the_migration_seeds_a_project_plan`:
`analytic.project_plan` valía `None`. Reproducido en serie: con
`tests/unit/orm/test_relational_reconstruction_persistence.py` (transaccional)
delante, el test cae; solo, pasa. El F2 de `5d7a9892` pasó porque xdist no
puso ningún test transaccional antes en ese worker.

Causa: `analytic/0017` siembra el plan, y un test `transaction=True` hace
`flush` de las tablas sin volver a aplicar la migración (H-API-22). El
catálogo `_SEEDERS` de `tests/conftest.py` repone las demás semillas de
migración; ésta no estaba.

## Referencia

- `odoo19c: addons/analytic/data/analytic_data.xml:13-17` — el plan «Project»
  y `analytic.project_plan`.

## Cambio

1. La siembra pasa a `addons/analytic/data/__init__.py` (`seed_project_plan`),
   con el mismo patrón que `addons/account/data/payment_methods.py`.
2. `analytic/0017` la llama; ya aplicada, su conducta no cambia.
3. `tests/conftest.py` la añade a `_SEEDERS` (`_project_plan_seed`).

## Símbolos, referencia y prueba

Prueba: `tests/unit/analytic/test_analytic_plan_methods.py::test_the_migration_seeds_a_project_plan`,
ejecutada detrás de un test transaccional.

| Símbolo | Referencia |
|---|---|
| `seed_project_plan`, `_main_company_id` | `odoo19c: addons/analytic/data/analytic_data.xml:13-17` |
| `0017_seed_project_plan` | `odoo19c: addons/analytic/data/analytic_data.xml:13-17` |
| `_project_plan_seed` | `odoo19c: addons/analytic/data/analytic_data.xml:13-17` |

## Control

Sin la entrada en `_SEEDERS` (el árbol de `892034dd`):
`1 failed, 5 passed`. Con ella: `15 passed` (el archivo entero detrás del
test transaccional).
