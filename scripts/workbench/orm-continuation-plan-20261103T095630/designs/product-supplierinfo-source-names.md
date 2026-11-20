# `product.supplierinfo`: los cinco nombres de la fuente

Unidad `product-supplierinfo-fk-names-0122` (TASK-API-0122), parte del
sucesor `product-fk-names-0122`.

## Contrato medido en la referencia

| Fuente | Línea | Este puerto |
|---|---|---|
| `product_uom_id = fields.Many2one('uom.uom', ...)` | `odoo19c: addons/product/models/product_supplierinfo.py:25` | `product_uom` |
| `company_id = fields.Many2one('res.company', ...)` | `odoo19c: addons/product/models/product_supplierinfo.py:33` | `company` |
| `currency_id = fields.Many2one('res.currency', ...)` | `odoo19c: addons/product/models/product_supplierinfo.py:36` | `currency` |
| `product_id = fields.Many2one('product.product', 'Product Variant', check_company=True)` | `odoo19c: addons/product/models/product_supplierinfo.py:42` | `product` |
| `product_tmpl_id = fields.Many2one('product.template', ..., required=True, ondelete='cascade')` | `odoo19c: addons/product/models/product_supplierinfo.py:47` | `product_tmpl` |

`partner_id` ya estaba en forma C (unidad `product-model-headers-0122`).

## Cambios

1. Los cinco pasan a su nombre de la fuente en forma C. Migración
   `0030_supplierinfo_source_names`: diez operaciones, todas `no-op` en
   `sqlmigrate`.
2. Dentro del modelo: `ProductSupplierinfo.clean`, `ProductSupplierinfo.save`,
   `ProductSupplierinfo.price_discounted`,
   `ProductSupplierinfo.product_variant_count` y
   `ProductSupplierinfo._get_filtered_supplier`. Las preguntas de presencia
   pasan a `_id_id`: `product_tmpl_id` es obligatorio y leer el registro
   sin valor lanza `RelatedObjectDoesNotExist` en vez de dar falso. Las
   comparaciones contra un entero (`company_pk`, `product_pk`) también.
3. Consumidores. El riesgo de este renombre es silencioso: el attname viejo
   (`seller.product_id`, entero) pasa a ser el registro, y
   `seller.product_id != self.pk` deja de fallar y empieza a mentir.
   Recorridos los receptores que llevan una tarifa (`seller`, `info`, `s`,
   `record`, `chosen`, `proveedor`, `supplier`, `elegidas`, `vendors`) en
   los archivos que nombran la tarifa:
   - `ProductProduct._prepare_sellers` (vía `_select_seller`),
     `ProductProduct._select_seller` (`sort_function`, `record.currency_id`) y
     la búsqueda del código del proveedor (`addons/product/models/
     product_product.py`);
   - `PurchaseOrderLine._compute_allowed_uom_ids`,
     `PurchaseOrderLine._compute_price_unit_and_date_planned_and_name`,
     `PurchaseOrderLine._suggest_quantity`
     (`addons/purchase/models/purchase_order_line.py`);
   - `PurchaseOrder._prepare_supplier_info` y `_add_supplier_to_product`
     (claves `currency_id`, `product_uom_id`);
   - `_get_replenishment_multiple_alternative`
     (`addons/purchase_stock/models/stock.py`), `_compute_display_name` de
     la tarifa (`addons/purchase_stock/models/product.py`) y el respaldo de
     `stock_rule.py` (`s.company_id_id`);
   - `addons/stock/models/stock_move.py`, `stock_move_line.py`,
     `stock_scrap.py` y `stock_orderpoint.py`: `getattr(proveedor,
     'product_uom', None)` habría devuelto `None` en silencio;
   - `PurchaseRequisitionLine` (`save` y `_create_supplier_info`,
     `addons/purchase_requisition/models/purchase_requisition.py`).
4. Contrato de borrado: el censo `outputs/fk_reference_ondelete.tsv` nombra
   los cinco por su nombre nuevo y `CORRECTED` cita
   `ProductSupplierinfo.company_id` y `.product_id` (lección de
   `product-pricelist-header.md`: el nombre viejo convertía la fila
   corregida en un `xfail` que ocultaba el `FieldDoesNotExist`).
5. `scripts/fk_naming_baseline.txt` retira las cinco líneas.

## Símbolos que cambian

- `ProductSupplierinfo.product_uom_id`, `ProductSupplierinfo.company_id`,
  `ProductSupplierinfo.currency_id`, `ProductSupplierinfo.product_id`,
  `ProductSupplierinfo.product_tmpl_id`;
- `clean`, `save`, `price_discounted`, `product_variant_count`,
  `_get_filtered_supplier`;
- `_prepare_sellers`, `_select_seller`, `_compute_allowed_uom_ids`,
  `_compute_price_unit_and_date_planned_and_name`, `_suggest_quantity`,
  `_prepare_supplier_info`, `_add_supplier_to_product`,
  `_get_replenishment_multiple_alternative`, `_compute_display_name`,
  `_create_supplier_info`;
- la migración `0030_supplierinfo_source_names`.

## Fuera de esta unidad, con su sucesor

- `ProductTemplate` (`categ`, `company`, `uom`), `ProductProduct.product_tmpl`
  y los de `combo`, `uom`, `document`, `product.template.attribute.*` —
  `product-fk-names-0122`.
- `purchase_requisition_line` sobre la tarifa (la fuente lo declara en
  `purchase_requisition`) — `purchase-requisition-fk-names-0122`.

## Pruebas

`tests/unit/product/test_product_supplierinfo_source_names.py`: los cinco
nombres con su columna; el filtro conserva las tarifas de la compañía y las
de ninguna, no las de otra; descarta las de otra variante; `save` deduce la
plantilla de la variante y siembra su unidad. Control de anulación: devolver
la comparación de compañía de `_get_filtered_supplier` al registro hace caer
exactamente esa prueba y `test_the_order_company_filters_the_sellers`
(2 failed, 23 passed).
