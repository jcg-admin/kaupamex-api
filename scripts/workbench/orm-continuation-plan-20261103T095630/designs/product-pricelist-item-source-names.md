# `product.pricelist.item`: los cuatro nombres de la fuente

Unidad `product-pricelist-item-fk-names-0122` (TASK-API-0122), parte del
sucesor `product-fk-names-0122` declarado en `product-pricelist-header.md`.

## Contrato medido en la referencia

| Fuente | Línea | Este puerto |
|---|---|---|
| `pricelist_id = fields.Many2one('product.pricelist', ...)` | `odoo19c: addons/product/models/product_pricelist_item.py:19` | `pricelist` |
| `product_tmpl_id = fields.Many2one('product.template', ...)` | `odoo19c: addons/product/models/product_pricelist_item.py:77` | `product_tmpl` |
| `product_id = fields.Many2one('product.product', ...)` | `odoo19c: addons/product/models/product_pricelist_item.py:82` | `product` |
| `base_pricelist_id = fields.Many2one('product.pricelist', 'Other Pricelist', check_company=True)` | `odoo19c: addons/product/models/product_pricelist_item.py:104` | `base_pricelist` |

`categ_id` ya estaba en forma C (unidad `product-model-headers-0122`).

## Cambios

1. Los cuatro pasan a su nombre de la fuente en forma C (`db_column` igual al
   nombre). Migración `0029_pricelist_item_source_names`: las ocho
   operaciones son `no-op` en `sqlmigrate` (las columnas ya tenían esos
   nombres).
2. `ProductPricelistItem.__str__` y `ProductPricelistItem.matches` leían el
   attname viejo (`pricelist_id`, `product_id`, `product_tmpl_id`, enteros).
   Con la forma C esos nombres son el registro, así que pasan a
   `pricelist_id_id`, `product_id_id` y `product_tmpl_id_id`.
   `ProductPricelistItem.clean` y `ProductPricelistItem.base_price_for` sólo
   preguntan si hay valor, y el registro responde igual.
3. Ningún otro módulo lee esos campos: búsqueda de `pricelist`,
   `product_tmpl`, `product`, `base_pricelist` como atributo, palabra clave o
   lookup en los archivos que nombran el item, y de sus accesores inversos
   (`item_ids`, `pricelist_rule_ids`, `derived_item_ids`). La extensión de
   `sale` (`addons/sale/models/product_pricelist_item.py`) sólo añade
   métodos.
4. `scripts/fk_naming_baseline.txt` retira las cuatro líneas y dos que ya
   estaban resueltas (`ProductPricelistItem.categ`,
   `ProductSupplierinfo.partner`).

El censo `outputs/fk_reference_ondelete.tsv` conserva los nombres viejos de
estas filas: ninguna entra en la población destructiva del contrato de
borrado (la fuente declara `cascade` en las tres primeras; `base_pricelist`
es `PROTECT`, no `CASCADE`), así que su nombre no se resuelve en ninguna
prueba.

## Símbolos que cambian

- `ProductPricelistItem.pricelist_id`, `ProductPricelistItem.product_tmpl_id`,
  `ProductPricelistItem.product_id`, `ProductPricelistItem.base_pricelist_id`;
- `ProductPricelistItem.__str__`, `ProductPricelistItem.matches`;
- la migración `0029_pricelist_item_source_names`.

## Fuera de esta unidad, con su sucesor

- `ProductSupplierinfo` (`company`, `currency`, `product`, `product_tmpl`,
  `product_uom`), `ProductTemplate` (`categ`, `company`, `uom`),
  `ProductProduct.product_tmpl` y los de `combo`, `uom`, `document` —
  `product-fk-names-0122`.

## Pruebas

`tests/unit/product/test_product_pricelist_item_source_names.py`: los
cuatro nombres con su columna; una regla de variante aplica a su variante y
no a otra; una regla de producto aplica a las variantes de su plantilla; la
regla se nombra por el id de su tarifa y aparece en `item_ids`. Control de
anulación: devolver la comparación de `matches` al registro hace caer
exactamente la prueba de variante (1 failed, 6 passed).
