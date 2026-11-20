# `product.category`: la cabecera de la fuente y `parent_id`

Unidad `product-category-header-0122` (TASK-API-0122), parte del sucesor
`product-model-headers-3-0122` declarado en `product-attribute-source-names.md`.

## Contrato medido en la referencia

`odoo19c: addons/product/models/product_category.py:9` a `:15` declara
`_name = 'product.category'`, `_inherit = ['mail.thread']`,
`_description = "Product Category"`, `_parent_name = "parent_id"`,
`_parent_store = True`, `_rec_name = 'complete_name'` y
`_order = 'complete_name'`. El padre es
`parent_id = fields.Many2one('product.category', ..., ondelete='cascade')`
(`odoo19c: addons/product/models/product_category.py:21`), con `child_id`
como One2many inverso (`:23`).

Este puerto no declaraba ningún atributo de clase y llamaba al padre `parent`.

## Cambios

1. `ProductCategory` declara los siete atributos verbatim. `_parent_store` en
   un modelo que no es `BaseModel` no activa `_maintains_parent_store`:
   `parent_path` lo sigue calculando `save()` (precedente `uom.uom`); lo que
   habilita es `child_of` por ruta en `orm/domains.py`. Como el modelo hereda
   de `TimeStampedModel`, `_name` no inyecta columnas de auditoría.
2. `parent` pasa a `parent_id` en forma C (`db_column='parent_id'`).
3. Migración `product/0027_category_source_header` (`sqlmigrate` medido):
   `AlterField` y `RenameField`, los dos `no-op` (la columna ya era
   `parent_id`).
4. Consumidores de `.parent` sobre la categoría:
   `ProductCategory.clean`, `ProductCategory.build_complete_name`,
   `ProductCategory.save`; `_get_category_account`
   (`addons/account/models/product.py`); `parent_route_ids`
   (`addons/stock/models/product.py`); `_get_putaway_strategy`
   (`addons/stock/models/stock_location.py`); `get_queryset` de
   `CategoryTreeView` (`addons/website_sale/controllers/main.py`, lookup
   `parent_id__isnull`). Las pruebas crean con `parent_id=`.

Búsqueda de consumidores: `grep` de `.parent`, `parent=`, `parent__` y
`'parent'` en los archivos que nombran `ProductCategory`, `product.category`
o `categ`; ningún XML/CSV de datos fija el padre de una categoría.

## Símbolos que cambian

- `ProductCategory._name`, `_inherit`, `_description`, `_parent_name`,
  `_parent_store`, `_rec_name`, `_order`
  (`odoo19c: addons/product/models/product_category.py:9`);
- `ProductCategory.parent_id`
  (`odoo19c: addons/product/models/product_category.py:21`);
- `ProductCategory.clean`, `build_complete_name`, `save`;
- `_get_category_account`, `parent_route_ids`, `_get_putaway_strategy`,
  `get_queryset`;
- la migración `0027_category_source_header`.

## Fuera de esta unidad, con su sucesor

- El hilo de `mail.thread`, `name_create`, `copy_data`
  (`odoo19c: addons/product/models/product_category.py:51`, `:61`) y el
  `_compute_display_name` con `hierarchical_naming` dependen de llevar el
  modelo a `BaseModel` — `product-category-mail-0122`.
- `product.pricelist` (`currency` → `currency_id`) y `product.document`
  (`_inherits` de `ir.attachment`) — `product-model-headers-3-0122`.

## Pruebas

`tests/unit/product/test_product_category_header.py`: la cabecera verbatim;
el registro resuelve `product.category`; `parent_id` con su nombre y su
columna; el árbol (`complete_name`, `parent_path`, `child_id`) se mantiene a
través de `parent_id`. Control de anulación: retirar `_name` hace caer
exactamente las dos pruebas que dependen de él (2 failed, 2 passed).
