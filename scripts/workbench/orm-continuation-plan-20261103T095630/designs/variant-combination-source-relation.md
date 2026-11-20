# Combinación de la variante: los nombres y las columnas de la fuente

Unidad `variant-combination-source-relation-0122` (TASK-API-0122),
prerrequisito de `pav-unlink-guard-0122`: la rama de archivo de
`product.attribute.value.unlink` lee las variantes de un valor por
`ptav_product_variant_ids`.

## Contrato medido en la referencia

- `odoo19c: addons/product/models/product_product.py:49`:
  `product_template_attribute_value_ids = fields.Many2many(
  'product.template.attribute.value', relation='product_variant_combination',
  ..., ondelete='restrict')`. Columnas derivadas: `product_product_id` y
  `product_template_attribute_value_id`.
- `:50-51`: `product_template_variant_value_ids`, la misma relación con
  dominio `attribute_line_id.value_count > 1` (otro campo sobre la misma
  tabla; medir si el puerto lo tiene).
- `odoo19c: addons/product/models/product_template_attribute_value.py:55-57`:
  `ptav_product_variant_ids`, el otro extremo, `readonly=True`.

## Estado del puerto (medido)

`ProductProduct.product_template_attribute_values` con
`db_table='product_variant_combination'` (la tabla ya es la de la fuente) y
`related_name='product_variant_ids'`. Columnas medidas en la intermedia:
`productproduct_id` y `producttemplateattributevalue_id`, las dos con
`CASCADE`. `product_template_variant_value_ids` no existe en el puerto. 23 usos del nombre del campo en 8 archivos y 3 del inverso
(`tests/integration/product/test_display_name_assignment.py`).

## Cambios

1. `product_template_attribute_values` → `product_template_attribute_value_ids`
   con `relation`, `column1`, `column2` de la fuente y
   `related_name='ptav_product_variant_ids'` (`Many2manyField`).
2. Los 23 usos y los 3 del inverso; las cadenas de `@api.depends` que lo
   nombran (`_compute_display_name`).
3. Migración de renombres; `sqlmigrate` comprueba que ninguna fila se mueve.
4. **`ondelete='restrict'` queda fuera, con sucesor.** En la fuente es la
   FK de `column2` de la intermedia (`odoo19c: odoo/orm/fields_relational.py:
   1253, 1363-1367`): no se borra un PTAV que alguna variante usa. El puerto
   cascada. `foreign-keys-delete-contract.md` dejó escrito que una
   intermedia automática no admite `on_delete`; sin embargo
   `Many2manyField` ya modifica la intermedia que genera (fija las
   columnas), así que el `PROTECT` de `column2` cabe ahí como mecanismo del
   ORM. Es una unidad propia, `many2many-column2-ondelete-0122`: en la
   fuente tres Many2many declaran un `ondelete` distinto de `cascade`.
5. `product_template_variant_value_ids` (`:50-51`) no se porta en esta
   unidad: es otro campo sobre la misma tabla con dominio, y Django expresa
   una tabla con un solo campo; su forma (propiedad filtrada) queda para la
   tarea de PTAV.

## Resultado medido

`makemigrations` propuso `RemoveField` + `AddField`, y su `sqlmigrate` era
`DROP TABLE "product_variant_combination" CASCADE` seguido de un
`CREATE TABLE`: borraba todas las combinaciones de variantes. Se reescribió
`0041_variant_combination_source_relation` como `RenameField` +
`AlterField`; su `sqlmigrate` sólo renombra las dos columnas
(`productproduct_id` → `product_product_id`,
`producttemplateattributevalue_id` → `product_template_attribute_value_id`)
y recrea sus FK. `makemigrations --check` no detecta diferencias.

## Símbolos que cambian

- `ProductProduct.product_template_attribute_value_ids`
  (`odoo19c: addons/product/models/product_product.py:49`), con su inversa
  `ProductTemplateAttributeValue.ptav_product_variant_ids`
  (`odoo19c: addons/product/models/product_template_attribute_value.py:55-57`);
- `ProductProduct.price_extra`, `ProductProduct.refresh_combination_indices`,
  `ProductProduct._compute_display_name` (cadena de `@api.depends`) y los
  lectores de `addons/product/services.py` y
  `addons/purchase/models/purchase_order_line.py`: leen el nombre de la
  fuente; la conducta no cambia;
- la migración `0041_variant_combination_source_relation`.

Pruebas: `tests/unit/product/test_variant_combination_source_relation.py`.
Control de anulación: devolver `related_name='product_variant_ids'` hace
caer exactamente la prueba de la inversa (1 failed, 1 passed).
