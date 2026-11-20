# `product_tmpl_id`: el nombre de la fuente en variante, BoM y línea

Unidad `product-tmpl-id-0122` (TASK-API-0122), parte del sucesor
`product-fk-names-0122`.

## Contrato medido en la referencia

| Modelo | Fuente | Este puerto |
|---|---|---|
| `product.product` | `product_tmpl_id = fields.Many2one('product.template', ...)` — `odoo19c: addons/product/models/product_product.py:42`, la FK de `_inherits` | `product_tmpl` |
| `mrp.bom` | `product_tmpl_id = fields.Many2one('product.template', ...)` — `odoo19c: addons/mrp/models/mrp_bom.py:31` | `product_tmpl` |
| `product.template.attribute.line` | `product_tmpl_id` — `odoo19c: addons/product/models/product_template_attribute_line.py:19` | `product_tmpl` |
| `stock.move`, `stock.quant`, `stock.warehouse.orderpoint` | `product_tmpl_id`, relacionado de `product_id.product_tmpl_id` | propiedad `product_tmpl` |

## Por qué los seis juntos

El nombre `product_tmpl` lo usan seis símbolos, y la fuente llama a los seis
`product_tmpl_id`. Renombrarlos en un mismo pase hace que el reemplazo
mecánico de `.product_tmpl` sea correcto en todo el árbol; renombrar sólo la
variante habría obligado a distinguir el receptor en cada uno de unos 260
puntos de lectura.

## Cambios

1. Los tres campos pasan a `product_tmpl_id` en forma C; las tres
   propiedades de `stock` se renombran igual. Migraciones
   `product/0033_product_tmpl_id` y `mrp/0008_product_tmpl_id`: los
   renombres son `no-op`; `product_product_combination_unique` y
   `unique_template_attribute` se rehacen sobre las mismas columnas, y el
   `ordering` de la variante pasa a `product_tmpl_id__name`.
2. Lecturas del attname viejo que comparaban enteros y pasan a
   `product_tmpl_id_id`: `ProductSupplierinfo.clean` (variante y plantilla
   de la tarifa), el asistente
   `purchase_requisition_create_alternative` y una prueba de
   `StockPutawayRule._default_product_id`. Sin ese cambio, `clean` habría
   comparado un registro con un entero y rechazado toda tarifa de variante.
3. Reemplazo mecánico en `addons`, `src` y `tests` (sin migraciones):
   `.product_tmpl`, `product_tmpl=`, `product_tmpl__`, `__product_tmpl` y la
   cadena `'product_tmpl'`/`'product_tmpl.` (dependencias, `select_related`,
   `ordering`, restricciones). La delegación de `_inherits`
   (`{'product.template': 'product_tmpl_id'}`) ya nombraba la clave por su
   nombre de la fuente; ahora la clave es el campo y no su attname.
4. El censo `outputs/fk_reference_ondelete.tsv` nombra las tres filas
   `product_tmpl_id`, y `CORRECTED` cita `mrp.MrpBom.product_tmpl_id`;
   `scripts/fk_naming_baseline.txt` retira las tres líneas.

## Símbolos que cambian

- `ProductProduct.product_tmpl_id`
  (`odoo19c: addons/product/models/product_product.py:42`),
  `MrpBom.product_tmpl_id` (`odoo19c: addons/mrp/models/mrp_bom.py:31`),
  `ProductTemplateAttributeLine.product_tmpl_id`;
- `StockMove.product_tmpl_id`, `StockQuant.product_tmpl_id`,
  `StockWarehouseOrderpoint.product_tmpl_id`;
- `ProductSupplierinfo.clean`;
- las migraciones `0033_product_tmpl_id` y `0008_product_tmpl_id`.

## Fuera de esta unidad, con su sucesor

- `ProductTemplate.uom` y los demás de `combo`, `uom`, `document` y
  `product.template.attribute.value` — `product-fk-names-0122`.

## Pruebas

`tests/unit/product/test_product_tmpl_id_source_name.py`: los tres nombres
con su columna; la variante lee su plantilla por `_inherits`; una tarifa
acepta una variante de su plantilla y rechaza la de otra. La red del
reemplazo mecánico es la batería entera.
