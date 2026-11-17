# Unidad 5 — `purchase-line-price-and-dates-0122`

Fuente: `odoo19c: addons/purchase/models/purchase_order_line.py`
(odoo-tools `abe4040ec1`). Plan: `designs/purchase-order-line-port.md`.

## Inventario medido antes de escribir

| Símbolo | Estado local | Acción |
|---|---|---|
| `date_planned` (`:25-28`) | ausente | campo `Datetime` calculado almacenado, `readonly=False`, `index`; migración + `ComputeStoredFields` |
| `_compute_price_unit_and_date_planned_and_name` (`:404-468`) | ausente | se porta; pasa a ser el `compute` de `name`, `price_unit`, `discount` y `date_planned` (como en la fuente: los cuatro son `store=True, readonly=False`) |
| `_get_date_planned` (`:334-351`) | ausente | se porta |
| `onchange_product_id` (`:366-380`) · `_product_id_change` (`:382-395`) | ausentes | se portan; `@api.onchange('product_id')` |
| `_reset_price_unit` (`:470-475`) | ausente | se porta (`update` de dos campos) |
| `_suggest_quantity` (`:535-551`) | ausente | se porta |
| `_get_product_purchase_description` (`:602-611`) | ausente | se porta |
| `_compute_tax_id` (`:146-152`) | ausente | se porta; usa `map_tax` y `_filter_taxes_by_company` (unidades ya asentadas) |
| `_convert_to_middle_of_day` (`:701-705`) | ausente | se porta; requiere `purchase.order.get_order_timezone` |
| `_date_in_the_past` (`:707-712`) | **ya portado** | sin cambio |
| `_update_date_planned` (`:714-715`) | ausente | se porta |
| `_compute_analytic_distribution` (`:353-364`) | ausente | **unidad propia**, ver abajo |

## `_compute_analytic_distribution` sale de esta unidad

En la fuente el override se dispara porque `analytic.mixin` declara
`analytic_distribution` con `compute='_compute_analytic_distribution'`,
`store=True`, `readonly=False` (`odoo19c: analytic/models/analytic_mixin.py`).
Aquí el mixin declara el campo **sin** `compute` (`addons/analytic/models/
analytic_mixin.py:77`): el override de `purchase` existiría y nadie lo
llamaría. Portar el contrato del mixin cambia el campo de **todos** sus
consumidores (líneas de venta, de factura, de compra…): es un mecanismo
transversal con su propio radio de verificación. Se registra como unidad
`analytic-mixin-distribution-compute-0121`, y el override de compra va con
ella.

## Precios: la protección de la fuente se conserva

El cómputo salta la línea cuando `technical_price_unit != price_unit`
(`:407`): un precio escrito a mano deja `technical_price_unit` atrás y el
cómputo no lo pisa. `_reset_price_unit` escribe los dos a la vez. Es la
única protección; no se añade otra.

## Divergencias declaradas

- `strftime(DEFAULT_SERVER_DATETIME_FORMAT)` (`:412`) existe en la fuente
  porque su caché guarda cadenas; aquí se asigna el `datetime`.
- `with_context(lang=…, seller_id=…)` sobre el producto: el contexto se
  aplica con `context_scope` sobre el mismo registro.

## Medido al implementar

- **Defecto del ORM, fuera de esta unidad.** Sobre una línea sin guardar,
  leer `line.date_order` (`fields.Datetime(related='order_id.date_order')`)
  levanta *Compute method failed to assign*, mientras que el `related`
  `Many2one` `line.currency_id` sí resuelve. Reproductor mínimo:

  ```python
  [o] = MODELS_BY_NAME['purchase.order'].create(
      [{'partner_id': v.pk, 'company_id': c.pk}])
  line = MODELS_BY_NAME['purchase.order.line'](
      order_id=o, name='x', product_qty=1, price_unit=1)
  line.currency_id   # MXN
  line.date_order    # ValueError
  ```

  Sospecha, sin medir: `BaseModel.__setitem__` (`src/orm/models.py:9708`)
  reparte la fila sin `pk` al cubo `new` y asigna sobre `self.browse(...)`,
  que puede no ser la instancia que se lee. Unidad registrada:
  `orm-related-scalar-unsaved-0485`. El cómputo lee la cadena
  `order_id.date_order`, que es lo que el `related` declara.
- `_select_seller` devuelve la lista de a lo sumo uno (`[:1]`);
  `_compute_selected_seller_id` asignaba la lista. Corregido aquí.
- `product_qty` es `Decimal` y `_get_filtered_sellers` compara con
  `float_compare`: el llamador convierte en la frontera.
- `product.template.currency`/`cost_currency` y el `default` de
  `product.supplierinfo.currency` se alinean con la fuente: sin ellos el
  precio no tiene moneda de origen.
