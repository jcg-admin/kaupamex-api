# Piloto de investigación concurrente: `purchase-line-qty-invoiced-0122`

Medido el 2026-11-17T02:56:43. Instrucción operativa 4.0.0, puntos 4-5 y 14.

## Ejecución

| Campo | Valor |
|---|---|
| TASK canónica | `TASK-API-0122` (store, sólo lectura: `pending`) |
| Unidad derivada | `purchase-line-qty-invoiced-0122` |
| Revisión de referencia | `odoo-tools@abe4040ec1` |
| Revisión del Consumer | `kaupamex-api@d0b8dacebe` |
| Lanzamiento | 2026-11-17T02:52:43Z, tres agentes `Explore` en paralelo, `run_in_background` |
| Restricción | sólo lectura: sin escrituras, sin git que cambie estado, sin PostgreSQL (un gate ci-multidb corría) |
| Cliente | Claude Code 2.1.326; `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` |

Las tres especialidades se cubrieron con el agente integrado `Explore` y un
prompt de rol, no con definiciones nuevas: los `.claude/agents/*.md` los
emite `@kaupamex/agent` en Thyrox, que esta VM no modifica, y ninguno de los
existentes coincide con los tres roles.

## Costo y tiempo

Costo en tokens equivalentes (`in` 1×, `cache_creation` 1.25×,
`cache_read` 0.1×, `out` 5×), sumado del `usage` de cada mensaje del
transcript. El titular del harness (74-76 k por agente) excluye `cache_read`.

| Agente | Modelo | Turnos | Herramientas | `cache_read` | equiv_cost | Pared |
|---|---|---|---|---|---|---|
| Odoo Contract Researcher | `claude-sonnet-5-5` | 8 | 6 | 358 560 | 249 516 | 116.4 s |
| ORM Port Auditor | `claude-sonnet-5-5` | 10 | 7 | 499 932 | 257 224 | 69.6 s |
| QA & Traceability Auditor | `claude-sonnet-5-5` | 10 | 7 | 456 080 | 304 817 | 72.7 s |
| **Total** | | 28 | 20 | | **811 557** | **116.4 s** |

*Métrica:* `usage` de los mensajes `assistant` de cada transcript.
*Ciega a:* el costo del coordinador al leer y cruzar los tres informes (no
medido por separado), y al precio efectivo bajo plan.

## Cruce contra el código (lo que el coordinador verificó)

| Hallazgo | Fuente | Veredicto |
|---|---|---|
| `qty_to_invoice` > 0 sólo con `order_id.state == 'purchase'` | Odoo | **confirmado** (`odoo19c: purchase_order_line.py:171`) |
| «Odoo cuenta `purchase` y `done`» | QA | **rechazado**: la fuente sólo compara con `'purchase'` |
| `invoicing_legacy` existe en el Consumer | ORM (no verificado) | **confirmado** (`addons/account/models/account_move.py:74`) |
| `AccountTax.compute_all` existe en el Consumer | ORM (no verificado) | **confirmado** (`addons/account/models/account_tax.py:626`) |
| `depends` por accessor inverso funciona | ORM (no verificado) | **confirmado** por uso existente (`addons/purchase/models/purchase_order.py:423`) |
| la unidad 3 usa `qty_received` (unidad 4) y `_get_gross_price_unit` (asignado a la unidad 5) pero sólo declara `dependsOn` related | QA | **confirmado** en `plan.jsonl` |
| `Uom._compute_quantity` hace `qty * self.factor` y `float_round`: con una cantidad `Decimal` falla o devuelve `float` | **ninguno** (lo halló el cruce) | **confirmado** (`addons/uom/models/uom_uom.py:363-392`) |

Hallazgos verificados: 6. Rechazados: 1. Duplicados: la evidencia de la
fuente aparece en dos informes (Odoo y ORM), sin contradicción.

## Comparación con la investigación secuencial

La línea base es el borrador secuencial de la unidad 3 escrito antes en esta
sesión (`scratchpad/test_purchase_line_qty_invoiced.py`, 9 pruebas, sin
costo medido aparte). El piloto añadió, verificado, lo que ese borrador no
cubría:

- un `in_receipt` u otro tipo de asiento no cuenta;
- sin facturas, `qty_invoiced` es 0;
- `qty_to_invoice` es 0 en `done` y `cancel`, no sólo en borrador, y puede
  ser negativo;
- `accrual_entry_date` igual a hoy no es «pasado» (`<` estricto) y una
  factura sin `invoice_date` queda fuera;
- `_get_invoice_lines` exige `ensure_one`;
- recálculo al cambiar el estado o la cantidad de la factura (`product_qty`
  no está en el `depends`, `product_uom_qty` sí);
- la dependencia real de la unidad 3 con las unidades 4 y 5.

**Veredicto del piloto.** Útil para esta clase de unidad: en 116 s de pared
produjo un contrato más completo que el borrador secuencial y una corrección
del plan. Costo: 811 557 tokens equivalentes, que no se amortiza en unidades
pequeñas ya estudiadas. Criterio que se sigue: delegar sólo unidades cuyo
contrato no se ha leído aún, y nunca repetir la lectura de lo ya cruzado.

## Corrección del plan aplicada

En `plan.jsonl`, la unidad `purchase-line-qty-invoiced-0122`:

- gana `dependsOn: purchase-line-qty-received-0122`, porque
  `_compute_qty_invoiced` lee `qty_received` (`odoo19c: :164-177`). Es el
  orden 4 → 3 que el diseño ya declaraba y el plan no;
- gana la obligación `_get_gross_price_unit`, que sale de
  `purchase-line-price-and-dates-0122`: la llama
  `_compute_amount_to_invoice_at_date` (`odoo19c: :280-285`), que es de la
  unidad 3. Así la obligación vive en la primera unidad que la necesita.
