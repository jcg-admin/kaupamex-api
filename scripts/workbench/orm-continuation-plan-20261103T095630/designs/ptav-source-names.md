# `product.template.attribute.value`: `attribute_line_id` y `product_attribute_value_id`

Unidad `ptav-source-names-0122` (TASK-API-0122), parte del sucesor
`product-fk-names-0122` y de la tarea de completar el porte de PTAV.

## Contrato medido en la referencia

- `odoo19c: addons/product/models/product_template_attribute_value.py:27-33`:
  `product_attribute_value_id = fields.Many2one('product.attribute.value',
  ..., required=True, ondelete='cascade')` y `attribute_line_id =
  fields.Many2one('product.template.attribute.line', required=True,
  ondelete='cascade', index=True)`.
- `odoo19c: addons/product/models/product_template_attribute_line.py:39-41`:
  la inversa en la línea es `product_template_value_ids`
  (`inverse_name='attribute_line_id'`).
- `product.attribute.value` no declara inversa hacia PTAV.

El puerto los llama `line` y `attribute_value`, sin `db_column` (columnas
`line_id` y `attribute_value_id`), y la inversa en la línea es
`template_values`. `_order` ya nombra los campos de la fuente.

## A diferencia de las unidades anteriores, las columnas cambian

Los campos no declaraban `db_column`, así que la forma C
(`attribute_line_id` con `db_column='attribute_line_id'`) renombra las
columnas: `line_id` → `attribute_line_id` y `attribute_value_id` →
`product_attribute_value_id`. La migración tiene que ser `RenameField` (que
emite `ALTER TABLE … RENAME COLUMN` y conserva los datos), nunca
`RemoveField` + `AddField`. La restricción `unique_template_attribute_value`
se reconstruye sobre los campos nuevos.

## Medición de lectores (subagente de lectura, verificada aquí)

Lecturas de `attname` entero (`<ptav>.line_id`, `.attribute_value_id`):
cero, comprobado con `grep`. Cadenas que no fallan al compilar:
`related='attribute_value.name'` (`name`) y el `@api.depends`
`'product_template_attribute_values.attribute_value.name'` de
`ProductProduct._compute_display_name`. Inversa `line.template_values`: 5
lecturas (`addons/product/services.py` 3, `tests/integration/sale/
test_product_attribute.py` 2). Creaciones y búsquedas con `line=` /
`attribute_value=`: `services.sync_template_values` y 15 llamadas en 5
archivos de prueba.

## Cambios

1. Los dos campos en forma C; `related_name` de `attribute_line_id` pasa a
   `product_template_value_ids` (el nombre de la inversa de la fuente).
2. `name` con `related='product_attribute_value_id.name'`; `__str__`;
   `Meta.ordering` y la `UniqueConstraint`.
3. `ProductProduct._compute_display_name` (cadena de `@api.depends`).
4. `services.sync_template_values` y los lectores de la inversa.
5. Pruebas que crean o buscan PTAV.
6. Censo, CORRECTED si los hay y `scripts/fk_naming_baseline.txt`.
7. El docstring del módulo (`:16-18`) que declaraba la divergencia de
   nombres.

## Pruebas

Nombre y columna de los dos campos; la inversa `product_template_value_ids`
en la línea; `name` se resuelve por el valor de atributo; la migración
conserva las filas (comprobado con `sqlmigrate`: `RENAME COLUMN`).
