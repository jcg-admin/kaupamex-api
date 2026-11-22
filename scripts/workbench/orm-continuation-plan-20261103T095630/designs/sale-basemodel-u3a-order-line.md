# U3a — `sale.order.line` sobre `BaseModel`

Segunda sub-unidad de la adopción de `BaseModel` en `sale`, tras U3-0
(ACL, `designs/sale-security-acl.md`). Insumo:
`outputs/sale-basemodel-adoption-research.md` (verificado en cuatro
afirmaciones, corregido en una).

## Por qué la línea antes que la orden

El accesor `order.order_line` sólo cambia de gestor a recordset cuando
**los dos** extremos son `BaseModel`. Adoptar primero la línea deja intactos
los 29 usos de gestor sobre `order_line` (que mueve U3b) y acota el cambio a
lo que la línea posee.

## Referencia

- `odoo19c: addons/sale/models/sale_order_line.py:13` — `_name`, con
  `_inherit = ['analytic.mixin']`.
- Borrado: la fuente no sobreescribe `unlink`; su recálculo de importes de la
  orden lo hace la dependencia de `amount_*` sobre `order_line`, y la guarda
  es `@api.ondelete(at_uninstall=False) _unlink_except_confirmed`
  (`:1469-1472`) con `_check_line_unlink` (`:1450-1466`).

## Decisión

1. `SaleOrderLine(models.BaseModel, AnalyticMixin, TimeStampedModel)`.
   `AnalyticMixin` y `TimeStampedModel` ya son abstractos (informe §1).
2. `delete()` (`addons/sale/models/sale_order_line.py:724-728`) pasa a
   `unlink()`: `BaseModel.unlink` borra por queryset y no llamaría al
   `delete()` de instancia, así que el recálculo `order._compute_amounts()`
   se perdería en silencio. `unlink` toma las órdenes antes de borrar y las
   recalcula después, una a una (`_compute_amounts` es de un registro).
   El recálculo por dependencia de la fuente no existe aquí para este
   borrado; el `unlink` lo sustituye y lo declara.
3. Los sitios que borran una línea por instancia pasan a `unlink()`
   (`addons/sale/services.py:265` y los que liste el subconjunto rojo).
4. Many2one nulos de la línea (`product`, `product_uom_id`,
   `combo_item_id`) pasan a recordset vacío: `is None` → falsedad
   (`addons/sale_stock_product_expiry/.../sale_order_line.py:37`).
5. Reversos hacia la línea desde modelos ya `BaseModel` pasan a recordset
   (`AccountMoveLine.sale_line_ids`, `account_move_line.py:30`, y los que
   liste el subconjunto rojo).

**Fuera de esta sub-unidad, con sucesor:** `_unlink_except_confirmed`,
`_check_line_unlink`, `create`/`write` propios de la fuente y
`@api.constrains('combo_item_id')` se portan en **U3c**
(`sale-unlink-guards-and-constraints-0397`), porque cambian comportamiento
observable (hoy una línea de orden confirmada se borra) y su prueba es otra.
No es una divergencia declarada: es el orden de los pasos.

## Símbolos, referencia y prueba

Prueba: `tests/unit/sale/test_sale_order_line_basemodel.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `SaleOrderLine` sobre `BaseModel` | `odoo19c: addons/sale/models/sale_order_line.py:13` | `test_the_line_is_a_base_model` |
| `SaleOrderLine.unlink` (recálculo de la orden) | `odoo19c: addons/sale/models/sale_order.py` `_compute_amounts` sobre `order_line` | `test_unlinking_a_line_recomputes_its_order` |
| Many2one nulo como recordset vacío | `odoo19c: odoo/orm/models.py` (`Many2one.convert_to_record`) | `test_a_line_without_product_has_an_empty_product` |

*Ciega a:* los reversos que sólo cambian al adoptar `SaleOrder` (U3b) y a la
plantilla DTL `docs.order_line.all` (`addons/sale/data/report_templates.py:57`),
que sigue siendo gestor hasta U3b.
