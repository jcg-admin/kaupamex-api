# Inventario contractual de `purchase.order.line`: unidades 5, 6 y checks

Medido el 2026-11-17T03:02:10 con el workflow `probes/workflows/orm-contract-inventory.js`
(run `wf_a79095f6-b2b`). Resultado completo:
`contract-inventory-purchase-line-wf_a79095f6.json`.

- Referencia: `odoo-tools@abe4040ec1`. Consumer: `kaupamex-api@c9e3eb66`.
- Universo: las 28 obligaciones que `plan.jsonl` declara para
  `purchase-line-checks-0122`, `purchase-line-price-and-dates-0122` y
  `purchase-line-lifecycle-0122` (TASK-API-0122). Sin exclusiones: el
  reconciliador repone como `UNVERIFIED` toda obligación que la
  investigación omita, y ninguna se omitió (`dropped: []`).

| Unidad | Declaradas | Satisfechas | Parciales | Ausentes | Divergentes | No verificadas |
|---|---|---|---|---|---|---|
| `purchase-line-checks-0122` | 2 | 0 | 0 | 2 | 0 | 0 |
| `purchase-line-price-and-dates-0122` | 13 | 0 | 1 | 12 | 0 | 0 |
| `purchase-line-lifecycle-0122` | 13 | 0 | 0 | 13 | 0 | 0 |
| **Total** | **28** | **0** | **1** | **27** | **0** | **0** |

El cruce corrigió una clasificación: `_compute_analytic_distribution` pasó de
`ABSENT` a `PARTIAL`, porque `PurchaseOrderLine` hereda `AnalyticMixin`
(`addons/purchase/models/purchase_order_line.py:52`), que lo define
(`addons/analytic/models/analytic_mixin.py:141`). El coordinador verificó esa
corrección y la ausencia de `create`, `write`, `_merge_po_line`,
`_prepare_account_move_line` y `date_planned` en la línea.

Lo que el inventario destapó y cambia el orden de trabajo:

- los dos CHECK de la línea (`_accountable_required_fields`,
  `_non_accountable_null_fields`) exigen la columna `date_planned`, que es
  de la unidad 5: la unidad de checks va después de la 5;
- el `_compute_product_uom_qty` local no deja en cero las filas de sección, y
  `_non_accountable_null_fields` las rechazaría con `product_qty` distinto
  de cero;
- `price_unit` local es `Monetary(12,2)` y no admite nulo, contra la
  semántica tri-valuada del CHECK de la fuente.

## Costo

| Ejecución | Obligaciones | Agentes | equiv_cost | Por obligación | Pared |
|---|---|---|---|---|---|
| Piloto (unidad 3) | 10 | 3 | 811 557 | 81 156 | 116 s |
| Workflow (unidades 5, 6, checks) | 28 | 6 | 1 570 440 | 56 087 | 156 s |

*Métrica:* `usage` de los transcripts de cada agente, `claude-sonnet-5-5`.
*Ciega a:* el costo del coordinador al cruzar los resultados, y a si las
pruebas que el inventario propone bastan: lo decide la implementación en TDD.
