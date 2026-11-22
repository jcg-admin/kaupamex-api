# U3b — `sale.order` sobre `BaseModel`

Tercera sub-unidad de la adopción de `BaseModel` en `sale`, tras U3-0 (ACL)
y U3a (la línea). Al adoptar la orden, `order.order_line` pasa de gestor a
recordset, porque sus dos extremos quedan en `BaseModel`. Insumo:
`outputs/sale-basemodel-adoption-research.md` §3.1-3.2.

## Referencia

- `odoo19c: addons/sale/models/sale_order.py:35` — `_name`; sus mixins ya
  son abstractos (informe §1).
- La fuente recorre `order_line` como recordset (`filtered`, `mapped`,
  `unlink`) y recalcula los importes por la dependencia de `_compute_amounts`
  sobre `order_line.*` (`addons/sale/models/sale_order.py:1122` aquí).

## Decisión

1. `SaleOrder(models.BaseModel, <bases actuales>)`.
2. **Los 29 usos de gestor sobre `order_line`** (informe §3.2, 16 archivos)
   pasan a la API de recordset de la fuente: iterar en vez de `.all()`,
   `filtered` en vez de `.filter`, `[:1]` en vez de `.first()`, `sorted` en
   vez de `.order_by`, y `filtered(...).unlink()` en vez de
   `.filter(...).delete()`. El alta por `order.order_line.create(**kw)` /
   `get_or_create` pasa a `SaleOrderLine.objects.create(order=order, ...)`,
   que es el gestor de la clase y no cambia.
3. **El recálculo explícito tras un borrado en bloque se mide, no se
   hereda.** El comentario de `addons/purchase/models/purchase_order.py:346-348`
   («este ORM no dispara `@api.depends`») es prosa de otro modelo y de otra
   época: U3a midió que `unlink` sí dispara la dependencia de
   `_compute_amounts`. Cada `order._compute_amounts()` que siga a un
   `filtered(...).unlink()` se retira si su anulación no cae, y se conserva
   (con su porqué) si cae.
4. **El descriptor DTL `docs.order_line.all`**
   (`addons/sale/data/report_templates.py:57`) lo siembra la migración
   `addons/sale/migrations/0002_seed_report_saleorder_view.py`: cambia a
   `docs.order_line` en el `.py` **y** en una migración de datos nueva, para
   que una base ya sembrada también lo reciba.
5. Many2one nulos de la orden con comodelo `BaseModel` (`team`,
   `journal_id`, `preferred_payment_method_line_id`, `pricelist_id`, UTM)
   pasan a recordset vacío: cada `is None` sobre ellos se reescribe por
   falsedad.
6. `addons/account/wizard/accrued_orders.py:223-224`: se mide si el `order`
   es de venta o de compra antes de tocarlo.
7. `'sale'` sale de `PENDING` en `tests/unit/orm/test_basemodel_reach.py`.

**Fuera de esta sub-unidad, con sucesor U3c** (`sale-unlink-guards-and-constraints-0397`):
`_unlink_except_draft_or_cancel`, `create` con secuencia, el `write` que
protege la tarifa y las dos `@api.constrains` de la orden, junto con las de
la línea.

## Símbolos, referencia y prueba

Prueba: `tests/unit/sale/test_sale_order_basemodel.py`.

| Símbolo | Referencia | Prueba |
|---|---|---|
| `SaleOrder` sobre `BaseModel` | `odoo19c: addons/sale/models/sale_order.py:35` | `test_the_order_is_a_base_model` |
| `order.order_line` como recordset | `odoo19c: addons/sale/models/sale_order.py` (`order_line = fields.One2many`) | `test_order_line_is_a_recordset_of_its_lines` |
| borrado en bloque de líneas recalcula el total | `_compute_amounts` con `@api.depends('order_line.…')` | `test_unlinking_lines_in_bulk_recomputes_the_order` |
| descriptor del reporte sin `.all` | `addons/sale/data/report_templates.py:57` + migración de datos | `test_the_report_template_iterates_the_recordset` |
| `sale` fuera de `PENDING` | `tests/unit/orm/test_basemodel_reach.py` | `test_the_pending_apps_are_exactly_the_measured_ones` |

*Ciega a:* los reversos desde modelos que aún no son `BaseModel` (stock,
payment, delivery, rating), que cambian cuando esas apps se adopten.
