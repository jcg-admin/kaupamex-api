# product-attribute-custom-value-basemodel-0397 — `product.attribute.custom.value` como `BaseModel`

Unidad hija de `basemodel-adoption-0397` (grupo `product`).

## Referencia

`odoo19c: addons/product/models/product_attribute_custom_value.py`
(25 líneas): cabecera (`:7-9`), `name` calculado sin columna (`:11`),
`custom_product_template_attribute_value_id` (`:12-16`, `ondelete=
'restrict'`), `custom_value` (`:17`) y `_compute_name` (`:19-25`), que
recorre el recordset y antepone el `display_name` del valor.

## Estado del puerto (medido 2026-11-21)

`TimeStampedModel` puro. `_compute_name` está escrito para un solo
registro y antepone `str(value)` en lugar de `display_name`, y devuelve el
nombre: se porta el cuerpo de la fuente. El `related_name='custom_values'`
no es de la fuente; se mide su uso antes de decidir.

`custom_values` no tiene consumidores (las coincidencias son el argumento
`custom_values` de `message_new` en `crm`): el inverso pasa a `'+'`, como la
fuente, que no lo declara.

## Implementación (2026-11-21)

`addons/product/models/product_attribute_custom_value.py`:
`ProductAttributeCustomValue` deriva de `(models.BaseModel,
TimeStampedModel)`; `ProductAttributeCustomValue._compute_name`
(`odoo19c: addons/product/models/product_attribute_custom_value.py:19-25`)
recorre el recordset y antepone el `display_name` del valor. El inverso de
`custom_product_template_attribute_value_id` pasa a `'+'`. **Migración
0053** `addons/product/migrations/0053_custom_value_basemodel.py`: sólo el
estado del inverso.

Pruebas: `tests/integration/product/test_product_attribute_custom_value.py`
espera ahora el `display_name` del valor (premisa del `str()` anterior) y
añade el cómputo de dos registros. Anulación: volver a `str()` y volver al
cuerpo de un solo registro tiran los dos casos del nombre. Limitar el
bucle al primer registro NO cambia el resultado: leer `name` recalcula
cada registro al acceder, así que esa mutación no es observable por la
lectura pública. Subconjunto derivado (product, sale): 635 passed.
