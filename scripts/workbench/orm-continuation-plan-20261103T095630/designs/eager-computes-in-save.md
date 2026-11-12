# Cómputos invocados por `save()` sobre campos calculados almacenados

Sucesor de `stored-computes-on-django-create.md` («Corrección de una
afirmación y duplicado medido»). Ocho modelos con calculados almacenados
declarados invocan sus métodos `_compute_*` dentro de `save()`.

## Contrato de la fuente

En Odoo 19 un calculado almacenado se calcula por el motor, nunca por la
sobrescritura de `create`/`write`:

- **creación**: los precompute los calcula `_add_precomputed_values`
  (`odoo19c: odoo/orm/models.py:4814-4846`) antes del INSERT; los demás, el
  `modified(..., create=True)` de `_create` (`:4930-4933`) y el volcado.
- **modificación**: `write` llama `modified(vals)` y el volcado recalcula los
  dependientes; la columna nueva llega en el `UPDATE` del `_flush`.

Las cinco cantidades de `sale.order.line` (`price_subtotal`, `price_tax`,
`price_total`, `price_reduce_taxexcl`, `price_reduce_taxinc`) son
`store=True, precompute=True` (`addons/sale/models/sale_order_line.py:190-209`)
y su `create` (`:1322`) no las toca.

## Lo que hace el árbol, por vía

`SaleOrderLine.save` (`addons/sale/models/sale_order_line.py:700-716`):

1. invoca `_compute_amount` y los dos `_compute_price_reduce_*`;
2. si llega `update_fields`, le añade las cinco columnas
   (`COMPUTED_AMOUNT_FIELDS`), para que un `save(update_fields=['price_unit'])`
   escriba también los importes;
3. `super().save()`; luego `self.order._compute_amounts()`.

| Vía | Cómputos antes del INSERT/UPDATE | Después | Duplicado |
|---|---|---|---|
| alta | `save()` + precompute de `pre_save` | 0 (el alta los protege) | **sí, 2 → debe ser 1** |
| modificación con `update_fields` | `save()` | 0: la escritura del cómputo descarta la marca (`Field.write` → `remove_to_compute`) | no |

La vía de modificación no duplica y tiene consumidores que dependen de que
la columna se escriba en el mismo `save()`: `addons/sale/services.py:249`
(`product_uom_qty`) y `:400` (`price_unit`), y
`addons/stock/models/stock_move.py:2148`. Retirar ahí el cálculo exigiría que
esos consumidores vuelquen antes de leer; no es parte de esta unidad.

## Corrección (por modelo)

**`SaleOrderLine`**: en alta (`self._state.adding`), no invocar los tres
cómputos: el precompute de `pre_save` ya los calcula sobre la misma fila,
después de `_coerce_amount_operands()`. En modificación, sin cambios.

Prueba RED (`tests/unit/sale/test_line_amount_computes_once.py`):

- alta por `objects.create`: `_compute_amount` corre **una** vez en total y
  los cinco importes persistidos son los de la línea;
- modificación con `save(update_fields=['price_unit'])`: la columna
  `price_subtotal` cambia en la base sin volcado previo (consumidor de
  `services.py:400`) y el cómputo corre una vez.

Anulación: restituir la llamada en alta hace caer exactamente el conteo de
alta.

**Los otros siete** (`CrmLead`, `SaleOrder`, `ResPartner`, `AccountAccount`,
`AccountMoveLine`, `AccountPaymentMethodLine`, `BaseAutomation`): mismo
procedimiento, modelo por modelo, con una pregunta previa que esta
investigación no cierra para ninguno: si el cómputo invocado es precompute
(lo calcula `pre_save`) o no (lo calcula el marcado de creación tras el
INSERT). En el segundo caso retirar la llamada en alta deja la columna sin
valor hasta el volcado, y un consumidor que lea la base justo después del
`save()` lo notaría; se mide con la suite derivada de cada modelo antes de
retirarla.

*Métrica:* llamadas al método por vía, con espía sobre la clase.
*Ciega a:* consumidores que lean la columna por SQL crudo sin volcar.
