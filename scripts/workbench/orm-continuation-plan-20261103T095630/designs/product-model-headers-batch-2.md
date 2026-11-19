# Cabeceras de cinco modelos de `product` que no exigen renombrar campos

Unidad `product-model-headers-2-0122` (TASK-API-0122), continuación de
`product-model-headers.md`. Paso previo de la adopción de `product` sobre
`BaseModel`.

## Contrato medido en la referencia

| Modelo | Fuente (`odoo19c: addons/product/models/`) | Cabecera |
|---|---|---|
| `product.attribute` | `product_attribute.py:8-12` | `_name`, `_description = "Product Attribute"`, `_order = 'sequence, id'` |
| `product.combo` | `product_combo.py:8-10` | `_name`, `_description = "Product Combo"`, `_order = 'sequence, id'` |
| `product.combo.item` | `product_combo_item.py:8-10` | `_name`, `_description = "Product Combo Item"`, `_check_company_auto = True` |
| `product.tag` | `product_tag.py:8-10` | `_name`, `_description = 'Product Tag'`, `_order = 'sequence, id'` |
| `product.uom` | `product_uom.py:9-11` | `_name`, `_description = 'Link between products and their UoMs'`, `_rec_name = 'barcode'` |

Cada campo que estas cabeceras nombran ya existe con su nombre (`sequence`,
`barcode`); `_check_company_auto` resuelve la empresa por
`COMPANY_FIELD_NAMES = ('company', 'company_id')` (`src/orm/models.py:1511`).
Los cinco derivan de `TimeStampedModel`, que ya trae las columnas de acceso
registrado: no hay migración (`makemigrations --check`: sin cambios).

## Cambios

1. Las cinco clases declaran su cabecera verbatim.

## Fuera de esta unidad, con su sucesor

Cinco cabeceras nombran campos que este puerto llama distinto o un mecanismo
que el modelo aún no tiene:

- `product.attribute.value` (`_order` con `attribute_id`; aquí `attribute`);
- `product.category` (`_parent_name = "parent_id"`, `_parent_store`,
  `_rec_name`/`_order` por `complete_name`; aquí `parent`);
- `product.pricelist` (`_rec_names_search` con `currency_id`; aquí
  `currency`);
- `product.template.attribute.line` (`_rec_name`/`_order` con
  `attribute_id`, `_rec_names_search` con `value_ids`; aquí `attribute` y
  `values`);
- `product.document` (`_inherits = {'ir.attachment': 'ir_attachment_id'}` y
  `_order` con `name`, que llega por la delegación; aquí `ir_attachment`).

Sucesor: `product-model-headers-3-0122`, con el renombre de esas FK a la
forma C como en `product-model-headers.md`.

## Pruebas

`tests/unit/product/test_product_model_headers_2.py`: las cinco cabeceras
verbatim.
