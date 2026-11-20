# `product.template.uom_id` y `product.uom.uom_id`: el nombre de la fuente

Unidad `product-template-uom-id-0122` (TASK-API-0122), parte del sucesor
`product-fk-names-0122`.

## Contrato medido en la referencia

- `odoo19c: addons/product/models/product_template.py:118` declara
  `uom_id = fields.Many2one('uom.uom', 'Unit', ...)`. `product.product` lo
  hereda por `_inherits` y lo lee como `uom_id`.
- `odoo19c: addons/product/models/product_uom.py:13` declara
  `uom_id = fields.Many2one('uom.uom', 'Unit', required=True, ondelete='cascade')`.

Este puerto llamaba a los dos `uom`, y la variante delegaba con una
propiedad `uom`. La columna ya era `uom_id` en las dos tablas.

## Cambios

1. `ProductTemplate.uom` → `ProductTemplate.uom_id` y `ProductUom.uom` →
   `ProductUom.uom_id`, en forma C. Migración `product/0034_uom_id`: cuatro
   operaciones `no-op` en `sqlmigrate` (`BEGIN; COMMIT;`).
2. `ProductProduct.uom` → `ProductProduct.uom_id`: la delegación por
   `_inherits` toma el nombre de la fuente.
3. Lecturas que eran el `attname` entero (`tmpl.uom_id`) pasan a
   `uom_id_id` antes del cambio de nombre: `StockMove` (unidades admitidas).
4. Lecturas del registro: todo `.uom`, `getattr(x, 'uom', None)`,
   `select_related('…uom')`, `__uom` y los argumentos `uom=` de las llamadas
   a `ProductTemplate`/`ProductUom` pasan a `uom_id`. Los `getattr` son el
   riesgo silencioso: con el nombre viejo devuelven `None` sin error.
   - `ProductPricelistItem.compute` (`convert`): una regla de precio fijo
     dejaría de convertir a la unidad pedida.
   - `ProductSupplierinfo` (unidad por defecto del proveedor),
     `StockMoveLine` (unidades admitidas), `StockLot` (unidad del lote).
   Consumidores tocados: `account_move_line`, `product_catalog_mixin`,
   `purchase/product`, `PurchaseOrder`, `PurchaseOrderLine`,
   `PurchaseRequisition`, `stock/product`, `StockMove`, `StockMoveLine`,
   `StockWarehouseOrderpoint`, `StockQuant`, `StockScrap`,
   `StockStorageCategory`, el controlador de `website_sale`.
5. Prosa que describía la divergencia (`uom` sin sufijo, `uom_id` como
   `attname`) se reescribe en `purchase/models/product.py`,
   `PurchaseOrderLine._compute_product_uom_qty`,
   `PurchaseOrderLine._compute_allowed_uom_ids` y
   `product_expiry/models/product_product.py`.
6. `scripts/fk_naming_baseline.txt` retira `ProductTemplate.uom` y
   `ProductUom.uom`; el censo `outputs/fk_reference_ondelete.tsv` nombra las
   dos filas `uom_id` (la trampa de `product-pricelist-header.md`).

## Corrección durante la unidad

La sustitución `\.uom\b` alcanzó dos literales que nombran el **modelo**,
no el campo: `_name = 'product.uom'` y la tabla de cabeceras de
`tests/unit/product/test_product_model_headers_2.py`, más dos docstrings.
Se devolvieron a `product.uom` antes de ejecutar la suite. Las claves
`'uom'` del contexto de evaluación de impuestos (`account_tax`,
`account_tax_python`) y de `PRICE_CONTEXT_KEYS` son claves de contexto de la
fuente y no cambian.

Búsqueda: `.uom`, `'uom'`, `"uom"`, `uom__`, `__uom`, `uom=` y
`product.uom` en `addons`, `src` y `tests`; ningún XML, CSV ni JSON de
datos nombra el campo.

## Símbolos que cambian

- `ProductTemplate.uom_id`
  (`odoo19c: addons/product/models/product_template.py:118`),
  `ProductUom.uom_id` (`odoo19c: addons/product/models/product_uom.py:13`),
  `ProductProduct.uom_id`;
- `ProductPricelistItem.compute`, `ProductSupplierinfo`, `StockMove`,
  `StockMoveLine`, `StockLot` y los consumidores del punto 4;
- lecturas del registro en: `ProductCatalogMixin._get_product_catalog_order_data`,
  `ProductCatalogMixin._get_product_catalog_order_line_info`,
  `ProductTemplate.uom_name`, `_compute_purchased_product_qty`,
  `_compute_template_purchased_product_qty`, `_update_uom` (`purchase`),
  `PurchaseOrderLine._compute_product_uom_qty`,
  `PurchaseOrderLine._compute_amount_to_invoice_at_date`,
  `PurchaseOrderLine._compute_price_unit_product_uom`,
  `PurchaseOrderLine._compute_allowed_uom_ids`, `_in_product_uom`,
  `_uom_change_is_blocked` (`stock/models/product.py`),
  `StockMove._create_backorder`,
  `StockMove._generate_serial_move_line_commands`,
  `StockMove._get_available_move_lines`,
  `StockMove._get_available_move_lines_in`,
  `StockMove._get_available_move_lines_out`, `StockMove._onchange_lot_ids`,
  `StockMove._prepare_move_line_vals`, `StockMove._set_lot_ids`,
  `StockMove._set_quantity_done_prepare_vals` (y su auxiliar
  `en_uom_del_movimiento`), `StockMove._split`,
  `StockMove._update_reserved_quantity_vals`,
  `StockMove.action_generate_lot_line_vals`,
  `StockMoveLine._compute_quantity`,
  `StockMoveLine._compute_quantity_product_uom`,
  `StockMoveLine._free_reservation`,
  `StockMoveLine._get_putaway_additional_qty`,
  `StockMoveLine._onchange_quantity`,
  `StockWarehouseOrderpoint._get_multiple_rounded_qty`,
  `StockWarehouseOrderpoint._get_orderpoint_action`,
  `StockScrap.action_validate`, `StockScrap.check_available_qty`. Cada una
  sólo cambia el nombre que lee (`.uom` → `.uom_id`); la conducta es la de
  la referencia, que lee `uom_id` en los mismos puntos;
- la migración `0034_uom_id`.

## Fuera de esta unidad, con su sucesor

- `ProductUom.product` y `ProductUom.company`, los campos de combo,
  `product.document.ir_attachment` y los de PTAV —
  `product-fk-names-0122`.

## Pruebas

`tests/unit/product/test_product_template_uom_id.py`: nombre y columna en
los dos modelos; la variante delega `uom_id`; una regla de precio fijo
convierte su precio a la unidad pedida (1 por unidad → 12 por docena).
Control de anulación: devolver el `getattr` de
`ProductPricelistItem.compute` a `'uom'` hace caer exactamente la prueba
de la conversión.
