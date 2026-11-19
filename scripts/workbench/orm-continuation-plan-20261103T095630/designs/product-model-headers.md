# Las cabeceras de `product.supplierinfo` y `product.pricelist.item`

Unidad `product-model-headers-0122` (TASK-API-0122). Su propósito declarado:
que las filas de acceso de `purchase` para estos dos modelos carguen.

## Contrato medido en la referencia

| Modelo | Fuente | Cabecera |
|---|---|---|
| `product.supplierinfo` | `odoo19c: addons/product/models/product_supplierinfo.py:8-11` | `_name`, `_description = "Supplier Pricelist"`, `_order = 'sequence, min_qty DESC, price, id'`, `_rec_name = 'partner_id'` |
| `product.pricelist.item` | `odoo19c: addons/product/models/product_pricelist_item.py:9-12` | `_name`, `_description = "Pricelist Rule"`, `_order = "applied_on, min_quantity desc, categ_id desc, id desc"`, `_check_company_auto = True` |

La cabecera nombra dos campos que este puerto llamaba distinto: `partner`
(≙ `partner_id`, `product_supplierinfo.py:11` y su campo) y `categ`
(≙ `categ_id`). Con el nombre viejo, `_rec_name` y `_order` no apuntaban a
ningún campo.

## Cambios

1. `ProductSupplierinfo` declara `_name`, `_description`, `_order` y
   `_rec_name` verbatim; el campo `partner` pasa a `partner_id` en forma C
   (`db_column='partner_id'`).
2. `ProductPricelistItem` declara `_name`, `_description` y `_order`
   verbatim; `categ` pasa a `categ_id` en forma C, también en
   `Meta.ordering` y en `ProductPricelistItem.matches`, que compara
   `categ_id.parent_path` como `_is_applicable_for` de la fuente.
3. Migración `product/0025_source_fk_names`: `AlterField` con `db_column` y
   `RenameField`, la forma de `crm/0002`. La columna ya se llamaba así:
   `sqlmigrate` da `no-op` en las cinco operaciones.
4. Consumidores del atributo (medidos con la suite derivada): las lecturas
   del entero pasan de `partner_id` a `partner_id_id`
   (`ProductProduct.code_for`, `partner_ref_for`, `_select_seller`,
   `_get_filtered_sellers`; `PurchaseOrder._add_supplier_to_product`;
   `PurchaseOrderLine` en sus dos filtros de proveedor), las del registro de
   `partner` a `partner_id` (`ProductSupplierinfo.__str__`,
   `_get_filtered_supplier`; `_compute_effective_vendor_id` y
   `_compute_display_name` de `purchase_stock`), y las altas y filtros de
   `ProductSupplierinfo` usan `partner_id=` (`_prepare_supplier_info`,
   `purchase_requisition`).
5. `purchase/security/ir.model.access.csv`: vuelven las dos filas de la
   fuente (`access_product_supplierinfo_purchase_manager`,
   `access_product_pricelist_item_purchase_manager`, `:31-32`), en su
   posición; el manifiesto actualiza la cuenta de omisiones (10 → 8) y
   `test_purchase_security_data.py` espera 27 filas.

## Fuera de esta unidad, con su sucesor

- `_check_company_auto = True` de `product.pricelist.item`: el modelo no
  declara `company_id`, que la fuente calcula y almacena
  (`product_pricelist_item.py:31`, `:173`).
- Los demás Many2one en forma A de los dos modelos (`product_uom`, `company`,
  `currency`, `product`, `product_tmpl`; `pricelist`, `product_tmpl`,
  `product`, `base_pricelist`).
  Sucesor de los dos puntos: `product-fk-names-0122`.

## Pruebas

`tests/unit/product/test_product_model_headers.py`: las dos cabeceras
verbatim; los dos campos con su nombre y su columna; las dos filas de
`purchase` cargadas; el nombre que muestra una tarifa es el de su proveedor
(`_rec_name`).
