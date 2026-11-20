# Líneas de atributo: las inversas y la tabla de la fuente

Unidad `attribute-line-source-relation-0122` (TASK-API-0122). Es la mitad
(a) del sucesor `pav-unlink-guard-0122` declarado en `ptav-source-names.md`:
la guarda de borrado de `product.attribute.value` lee las líneas que usan
el valor por `pav_attribute_line_ids`, y ese nombre no existe en el puerto.
La mitad (b) —adopción de `BaseModel`, `active`, la guarda, el archivo en
`unlink` y el `cascade` de PTAV— queda en `pav-unlink-guard-0122`.

## Contrato medido en la referencia

- `odoo19c: addons/product/models/product_template_attribute_line.py:32-36`:
  `value_ids = fields.Many2many('product.attribute.value',
  relation='product_attribute_value_product_template_attribute_line_rel',
  ...)`. Sin `column1`/`column2`, Odoo las deriva de las tablas:
  `product_template_attribute_line_id` y `product_attribute_value_id`.
- `odoo19c: addons/product/models/product_attribute_value.py:29-33`:
  `pav_attribute_line_ids`, el otro extremo de la misma tabla.
- `odoo19c: addons/product/models/product_attribute.py:59-62`:
  `attribute_line_ids`, la inversa de `attribute_id` en la línea.

## Estado del puerto (medido)

`ProductTemplateAttributeLine.value_ids` usa la tabla que Django genera,
`product_template_attribute_line_value_ids`, y `related_name='template_lines'`;
`attribute_id` también tiene `related_name='template_lines'`. Lectores: 4
pruebas (`color.template_lines` es la del atributo; `red.template_lines` y
`valores[0].template_lines`, la del valor).

## Cambios

1. `value_ids` con `relation`, `column1` y `column2` de la fuente
   (`Many2manyField`, `src/orm/fields_relational.py`) y
   `related_name='pav_attribute_line_ids'`.
2. `attribute_id` con `related_name='attribute_line_ids'`.
3. Los cuatro lectores de prueba.
4. Migración: la tabla y sus dos columnas se **renombran**; ninguna fila se
   pierde. Si `makemigrations` propone recrear la intermedia, se escribe a
   mano con `SeparateDatabaseAndState` (`RENAME TABLE` + `RENAME COLUMN`
   en la base, el campo nuevo en el estado), y `sqlmigrate` lo comprueba.

## Pruebas

Tabla y columnas de la intermedia con los nombres de la fuente; las dos
inversas; una relación existente sobrevive a la migración (lo comprueba
`sqlmigrate`: sólo renombres).
