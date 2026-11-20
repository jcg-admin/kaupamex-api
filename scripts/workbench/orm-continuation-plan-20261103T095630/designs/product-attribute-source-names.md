# `attribute_id` y `value_ids`: dos cabeceras de `product` que nombran campos renombrados

Unidad `product-attribute-fk-names-0122` (TASK-API-0122), parte del sucesor
`product-model-headers-3-0122` declarado en `product-model-headers-batch-2.md`.

## Contrato medido en la referencia

| Modelo | Fuente (`odoo19c: addons/product/models/`) | Cabecera | Campos que nombra |
|---|---|---|---|
| `product.attribute.value` | `product_attribute_value.py:12-14` | `_name`, `_order = 'attribute_id, sequence, id'`, `_description = "Attribute Value"` | `attribute_id` |
| `product.template.attribute.line` | `product_template_attribute_line.py:12-16` | `_name`, `_rec_name = 'attribute_id'`, `_rec_names_search = ['attribute_id', 'value_ids']`, `_description`, `_order = 'sequence, attribute_id, id'` | `attribute_id`, `value_ids` |

Este puerto llamaba a esos campos `attribute` (en los dos modelos) y
`values` (el Many2many de la línea).

## Cambios

1. Las dos clases declaran su cabecera verbatim.
2. `attribute` pasa a `attribute_id` en forma C (`db_column='attribute_id'`)
   en los dos modelos; `values` pasa a `value_ids`. Las restricciones únicas,
   `ProductAttributeValue.__str__` y `ProductTemplateAttributeLine.__str__`
   siguen el nombre nuevo.
3. Migración `product/0026_attribute_source_names` (`sqlmigrate` medido): las
   dos FK son `no-op` (la columna ya se llamaba `attribute_id`); la tabla del
   Many2many pasa de `product_template_attribute_line_values` a
   `product_template_attribute_line_value_ids` con sus filas; las dos
   restricciones únicas se rehacen sobre las mismas columnas.
4. Consumidores: `sync_template_values` y su vecino en
   `addons/product/services.py` leen `line.value_ids`; las pruebas crean con
   `attribute_id=` y fijan `line.value_ids`.

## Fuera de esta unidad, con su sucesor

- `product.category`, `product.pricelist` y `product.document` (renombres de
  `parent`, `currency` e `ir_attachment`, más `_parent_store` e `_inherits`) —
  `product-model-headers-3-0122`.
- Las lecturas `value.attribute_id.name` sobre
  `product.template.attribute.value` en `account_edi_ubl_cii` y en
  `PurchaseOrderLine` nombran un campo que ese modelo aún no declara aquí
  (la fuente lo declara relacionado de `attribute_line_id.attribute_id`) —
  `ptav-attribute-related-0122`.

## Pruebas

`tests/unit/product/test_product_attribute_source_names.py`: las dos
cabeceras verbatim; los campos con su nombre y su columna; el nombre que
muestra una línea es el de su atributo (`_rec_name`).
