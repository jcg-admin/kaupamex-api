# Revisión del grafo y del universo de `purchase.order.line`

Medido el 2026-11-17T03:10:55 por el coordinador, sin agentes: AST de la fuente, `grep` y
`plan.jsonl`. Referencia `odoo-tools@abe4040ec1`.

## Universo: la fuente contra el plan (instrucción 4.1.0, punto 5)

`PurchaseOrderLine` declara **96** símbolos (métodos y asignaciones de clase)
en `odoo19c: addons/purchase/models/purchase_order_line.py`. El plan nombra
**83**: ninguno que la fuente no tenga y ninguno en dos unidades. **13** no
estaban en ninguna unidad:

`_compute_product_uom_qty`, `_compute_selected_seller_id`, `_description`,
`_get_select_sellers_params`, `_order`, `company_id`, `discount`, `name`,
`order_id`, `price_unit`, `product_id`, `product_qty`, `product_uom_qty`.

Los 13 existen en el Consumer (unidades anteriores los portaron sin
declararlos), pero existir no es satisfacer: `_compute_product_uom_qty` no
deja en cero las filas de sección y `price_unit` es `Monetary(12,2)` sin
nulo. Quedan en la unidad nueva `purchase-line-core-0122` (TASK-API-0122),
**no verificados** hasta que se contrasten. No se reescribió ninguna unidad
aceptada.

## `_compute_analytic_distribution`: el workflow lo dio PARCIAL; es AUSENTE

Lo que la línea hereda en el Consumer es el método **vacío** del mixin
(`addons/analytic/models/analytic_mixin.py:141`, ≙ `odoo19c:
analytic/models/analytic_mixin.py:77-78`, `pass`). La fuente lo
**sobrescribe** en Purchase con un cálculo real: `@api.depends('product_id',
'order_id.partner_id')`, omite las filas con `display_type` y busca la
distribución en `account.analytic.distribution.model._get_distribution` con
producto, categoría, socio, categorías del socio y empresa. Esa sobrescritura
no existe en el Consumer. El cruce del workflow aceptó la herencia como
satisfacción parcial; es el caso «heredar no es satisfacer». En el inventario
de las unidades 5, 6 y checks el conteo correcto es **28 ausentes, 0
parciales**.

## Grafo de dependencias (punto 6)

| Decisión | Evidencia |
|---|---|
| `_get_gross_price_unit` se implementa en la unidad 3 | sus llamadores en la fuente son `_compute_amount_to_invoice_at_date` (unidad 3, `:285`) y el asistente de devengos de `account` (`account/wizard/accrued_orders.py:184-251`, consumidor dependiente bajo TASK-API-0121). La unidad 5 **no** lo llama. Lo que necesita —`price_unit`, `discount`, `tax_ids.compute_all`, factores de unidad— ya existe por las unidades 1 y 2. Propietario: la unidad 3, porque allí sus dependencias están satisfechas. |
| `purchase-line-checks-0122` depende de `purchase-line-price-and-dates-0122` | los dos CHECK nombran `date_planned` dos veces (`:98-105`), y ese campo es de la unidad 5. El plan sólo declaraba `purchase-product-0397`; se añadió la arista. |
| `purchase-line-qty-invoiced-0122` depende de `purchase-line-qty-received-0122` | `_compute_qty_invoiced` lee `qty_received` (`:164-177`); corregido en `c9e3eb66`. |
| Ciclos | ninguno en las 277 filas del plan; ninguna dependencia a una unidad inexistente. |

## Decimal y UoM (punto 8)

Medido con instancias de `uom.Uom` en memoria (sin base):

```text
float 3.0              -> 36.0
Decimal 3              -> TypeError unsupported operand type(s) for *: 'decimal.Decimal' and 'float'
Decimal 2.5000         -> TypeError (idem)
misma unidad, Decimal  -> TypeError (idem)
```

- **Con `float` el núcleo local coincide con la fuente**, que declara
  `qty: float` y `factor` `Float` (`odoo19c: uom/models/uom_uom.py:147-176`):
  la fuente nunca recibe `Decimal`.
- **El fallo es de frontera**: en el Consumer toda cantidad es `Decimal`
  por convención (`product_qty`, `account.move.line.quantity`), y el núcleo
  de UoM es `float`. Los llamadores actuales convierten antes
  (`addons/purchase/models/purchase_order_line.py:244`, `float(...)`).
  Es del núcleo de UoM, no de Purchase.
- **Arreglo que corresponde** (en `addons/uom`, después del gate): conservar
  el tipo de entrada, `Decimal` adentro y `Decimal` afuera, con `factor` y
  `rounding` llevados a `Decimal`. Pasarlo todo a `float` perdería los cuatro
  decimales almacenados.
- **Huecos del porte del núcleo, ajenos al tipo:** faltan la guarda
  `if not self`, el `ensure_one()` y el parámetro `raise_if_failure` de la
  fuente.
