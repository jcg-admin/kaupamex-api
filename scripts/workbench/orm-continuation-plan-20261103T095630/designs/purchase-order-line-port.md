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
