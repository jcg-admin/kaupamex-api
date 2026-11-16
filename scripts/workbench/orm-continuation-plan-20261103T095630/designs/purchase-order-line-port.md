# Porte completo de `purchase.order.line` — descomposición en unidades

Fecha: 2026-11-16T03:32:07 · TASK-API-0122 (Capa 1 purchase).
Fuente: `odoo19c: addons/purchase/models/purchase_order_line.py`
(odoo-tools@HEAD de la sesión; LGPL-3 por `__manifest__.py`).

## Medición que la origina

Al planear `purchase-product-actions-0397` (las acciones `action_view_po` de
`product.py`), la vista que la acción abre (`purchase_history_tree`,
`purchase_views.xml:819-837`) nombra campos de la línea que este árbol no
tiene: `state`, `date_approve`, `price_unit_product_uom`, `action_open_order`.
Contar por AST los símbolos de la clase (campos públicos y métodos) contra
`addons/purchase/models/purchase_order_line.py`:

| Archivo de la fuente | símbolos | ausentes aquí |
|---|---|---|
| `purchase_order_line.py` | 90 | **67** |
| `purchase_order.py` | 129 | **91** |

*Métrica:* nombres de `FunctionDef` y de `Assign` público de cada clase,
buscados como texto en el puerto.
*Ciega a:* un símbolo presente con nombre pero con otra forma (p. ej.
`price_total` es aquí un **método** y en la fuente un `Monetary` almacenado;
cuenta como presente). Es cota inferior de lo que falta.

Además, divergencias de forma ya presentes y no declaradas como tales en la
fuente: `product_qty` es `PositiveIntegerField` (la fuente: `Float`,
`digits='Product Unit'`); `price_unit` y `discount` son `Monetary` (fuente:
`Float`); `name` es `Char` (fuente: `Text`, calculado almacenado);
`price_subtotal`/`price_total`/`price_tax` son métodos con un IVA fijo
(`get_setting('iva_rate')`), cuando la fuente los calcula con
`account.tax` sobre `tax_ids` (`:107-117`). El motor que la fuente usa ya
existe aquí: `account_tax.py::_prepare_base_line_for_taxes_computation`,
`_add_tax_details_in_base_line`, `_round_base_lines_tax_details`.

Consumidores de los métodos de importe que el porte debe migrar:
`addons/purchase_requisition/models/purchase.py:400` (`price_subtotal()`) y
`tests/unit/purchase_requisition/test_get_tender_best_lines_currency.py`.

## Unidades (todas TASK-API-0122, en `plan.jsonl`)

1. `purchase-line-amounts-0122` — `tax_ids`, tipos de `product_qty`,
   `price_unit`, `discount`; `_compute_amount` y
   `_prepare_base_line_for_taxes_computation`; `price_subtotal`,
   `price_total`, `price_tax` almacenados; migrar consumidores.
2. `purchase-line-related-0122` — `state`, `date_order`, `date_approve`,
   `currency_id` (related, hoy `@property`), `product_type`,
   `tax_calculation_rounding_method`, `product_template_attribute_value_ids`,
   `product_no_variant_attribute_value_ids`, `translated_product_name`,
   `price_unit_product_uom`, `price_unit_discounted`, `technical_price_unit`,
   `parent_id`, `allowed_uom_ids`, `name` como `Text`.
3. `purchase-line-qty-invoiced-0122` — `invoice_lines`, `qty_invoiced`,
   `qty_to_invoice`, `_prepare_qty_invoiced`, `_get_invoice_lines`,
   `qty_invoiced_at_date`, `amount_to_invoice_at_date`.
4. `purchase-line-qty-received-0122` — `qty_received_method`,
   `qty_received`, `qty_received_manual`, `_inverse_qty_received`,
   `_track_qty_received`, `qty_received_at_date`.
5. `purchase-line-price-and-dates-0122` — `date_planned`,
   `_compute_price_unit_and_date_planned_and_name`, `_get_date_planned`,
   `onchange_product_id`, `_product_id_change`, `_reset_price_unit`,
   `_get_gross_price_unit`, `_suggest_quantity`,
   `_get_product_purchase_description`, `_compute_tax_id`,
   `_compute_analytic_distribution`, `_convert_to_middle_of_day`,
   `_date_in_the_past`, `_update_date_planned`.
6. `purchase-line-lifecycle-0122` — `create`, `write`,
   `_unlink_except_purchase`, `_merge_po_line`, `get_parent_section_line`,
   `action_open_order`, `action_add_from_catalog`,
   `_get_product_catalog_lines_data`, `_prepare_account_move_line`,
   `_prepare_add_missing_fields`, `_prepare_purchase_order_line`,
   `_compute_purchase_line_warn_msg`.

Orden: 1 → 2 → (3, 4) → 5 → 6. `purchase-line-checks-0122` (los dos CHECK)
va tras 5, porque `date_planned` es parte del CHECK de líneas contables.
`purchase-analytic-validation-0397` va tras 6. `purchase-product-actions-0397`
(las cinco piezas de `product.py`) va tras 2 y necesita además el campo
`property_purchase_currency_id` de `res.partner` y la base
`_get_backend_root_menu_ids` (`odoo19c: mail/models/models.py:863-871`).

`purchase.order` (91 ausentes) se descompone en su propio diseño cuando la
línea esté completa; sus importes dependen de la unidad 1.

## Unidad 1 — `purchase-line-amounts-0122` (2026-11-16T03:54:33)

Contrato (`odoo19c: purchase_order_line.py:23,34,38-40,46-48,106-143`):

- `tax_ids = fields.Many2many('account.tax', …)`: tabla por defecto de la
  fuente, `'%s_%s_rel' % tuple(sorted(tablas))` (`fields_relational.py:1291`)
  → `account_tax_purchase_order_line_rel`, columnas
  `purchase_order_line_id` y `account_tax_id`.
- `product_qty`: `Float(digits='Product Unit', required=True)`, **sin
  default**. El `PositiveIntegerField(default=1, MinValue(1))` de aquí
  inventa un default y un mínimo que la fuente no tiene; un pedido de 2.5 kg
  no cabía. Se declara como `quantity` de `account.move.line`
  (`Monetary(max_digits=16, decimal_places=4)`): mismo `digits='Product
  Unit'`, mismo mecanismo de pila (`Decimal`), ya declarado en ese archivo.
- `price_subtotal`, `price_total` (`Monetary`) y `price_tax` (`Float`):
  `compute='_compute_amount', store=True`. Divergencia de pila declarada,
  la misma que `sale.order.line`: `price_tax` va en `Monetary` porque el
  motor y los importes son `Decimal`.
- `_compute_amount` y `_prepare_base_line_for_taxes_computation` sobre el
  motor de `account.tax` que ya existe (`account_tax.py:1102,1222,1877`),
  que trabaja en `Decimal`.

Lo que sale de esta unidad: el IVA fijo (`get_setting('iva_rate')`). Con
la fuente, una línea sin `tax_ids` no lleva impuesto, y una con un IVA del
16 % incluido en el precio da 200 + 32 = 232.

Consumidores que cambian en el mismo pase: `PurchaseOrder._sum_lines`
(llamaba `getattr(line, attr)()`), `purchase_requisition/models/
purchase.py:400` (`price_subtotal()`), y las 16 creaciones de línea en
pruebas que omiten `product_qty` (medido por un recorrido de las llamadas
`create(`; la fuente lo exige).

Fuera de la unidad, con sucesor:

- `amount_untaxed`/`amount_tax`/`amount_total` de la orden siguen como
  métodos que suman las columnas: el `_amount_all` de la fuente
  (`purchase_order.py:29-44`) usa `_get_tax_totals_summary`, que **no existe**
  aquí (`grep -n "def _get_tax_totals_summary" addons/account` → 0).
  Sucesores: `account-tax-totals-summary-0121` y
  `purchase-order-amounts-0122`.
- `price_unit` y `discount` son calculados almacenados en la fuente
  (`_compute_price_unit_and_date_planned_and_name`); el cómputo es la
  unidad 5.

### Medido al implementar la unidad 1

- `price_total_cc` de `purchase_requisition` se calculaba en `save()`
  (tarea #191, cuando el ORM no tenía motor de `@api.depends`). Con
  `price_subtotal` como calculado almacenado, `save()` lo leía antes de que
  se calculara y daba 0. Se porta como en la fuente: calculado almacenado con
  `@api.depends('price_subtotal', 'order_id.currency_rate')`
  (`odoo19c: purchase_requisition/models/purchase.py:257-263`), y la
  migración 0017 lo recalcula.
- `product_uom_qty` es `Float` y `product_qty` ahora `Decimal`: el cómputo
  convierte con `float()` (`uom._compute_quantity` multiplica `float`).
- Pruebas que creaban órdenes sin `company_id` o líneas sin `product_qty`:
  la fuente exige los dos (`purchase_order.py:155`, `purchase_order_line.py:
  23`); se completaron los datos de prueba, no el código.
- Control de anulación: con `tax_ids=self.tax_ids.none()` en
  `_prepare_base_line_for_taxes_computation` caen exactamente 6 de los 9
  casos de `test_purchase_line_amounts.py` (los que tienen impuesto y la
  migración); sobreviven la tabla, el campo de cantidad y la línea sin
  impuestos.

## Unidad 2 — `purchase-line-related-0122` (2026-11-16T04:14:14)

Contrato (`odoo19c: purchase_order_line.py:19-21,35,38,42-45,54,85-90,
105-111,152-162,229-235,467-472,510-529`):

| Símbolo | Fuente | Aquí |
|---|---|---|
| `state` | `related='order_id.state'` | related sin columna |
| `date_order`, `date_approve` | related de la orden, `readonly` | related sin columna |
| `currency_id` | `related='order_id.currency_id'` | hoy `@property`; pasa a related (es el campo de moneda de los `Monetary`) |
| `product_type` | `related='product_id.type'` | related; `type` vive en `product.template` y `product.product` lo hereda por `_inherits` |
| `tax_calculation_rounding_method` | `related='company_id.tax_calculation_rounding_method'` | related; el campo lo añade `account` a `res.company` (`account/models/res_company.py:701`) |
| `product_template_attribute_value_ids` | `related='product_id.product_template_attribute_value_ids'` | related a `product_template_attribute_values`, el nombre que el porte de `product.product` usa (divergencia de nombre ajena, de `product-model-headers-0122`) |
| `product_no_variant_attribute_value_ids` | `Many2many('product.template.attribute.value', ondelete='restrict')` | tabla por defecto de la fuente: `product_template_attribute_value_purchase_order_line_rel` |
| `translated_product_name` | `compute` con `lang` del proveedor | sin columna |
| `price_unit_product_uom` | `compute`, `uom._compute_price` | sin columna |
| `price_unit_discounted` | `compute` | sin columna |
| `technical_price_unit` | `Float` almacenado | `Monetary` (precio en `Decimal`, como `price_unit`) |
| `parent_id` | `compute='_compute_parent_id'` | sin columna |
| `allowed_uom_ids` | `compute`, unidades del producto y de sus tarifas | sin columna; la tarifa nombra su unidad `product_uom` |
| `name` | `Text`, calculado almacenado | `Text` aquí; el cálculo es la unidad 5 |

Las cifras que el diseño deja como cota: `display_type` es `Selection` con
`null=True` y la fuente usa `False`; las comparaciones `not line.display_type`
cubren las dos.

### Medido al implementar la unidad 2

- `product_type` sigue la cadena `product_id.product_tmpl.type`: el porte de
  `product.product` delega `type` con una propiedad, no con un campo, y el
  recorrido del related lee campos (`KeyError: 'type'`).
- Un `related` que termina en un `Many2many` de un modelo de Django leía el
  gestor relacionado, no iterable; la fuente lee el recordset. Corregido en
  `orm.fields._end_of_chain`, con su prueba
  (`tests/unit/orm/test_related_many2many_end_of_chain.py`).
- `translated_product_name` lee `display_name` bajo
  `context_scope(lang=…)`: `product.product` es un modelo de Django sin
  `with_context`.
- `parent_id` asigna `None` donde la fuente asigna `False`: el Many2one de
  este ORM rechaza `False`.
- `price_unit_discounted` con descuento 0: `discount or 0` daba `1 - 0/100`
  en `float` y `Decimal * float` fallaba; caso añadido.
- **Hueco del ORM, sucesor `orm-nonstored-compute-on-new-records-0397`:**
  ningún calculado o related sin columna se lee sobre un registro de
  `new()` (medido en `test_orm.multi.name`,
  `purchase.order.lock_confirmed_po` y los related de esta línea). La
  prueba de la propiedad retirada `currency_id` queda como `xfail` estricto
  que nombra el sucesor.
- Control de anulación del arreglo del ORM: retirada la rama del `Manager`
  en `_end_of_chain`, caen exactamente 2 casos —el de
  `test_related_many2many_end_of_chain.py` y el de los related de producto
  y empresa de la línea— y pasan los otros 11 de esos dos archivos.
